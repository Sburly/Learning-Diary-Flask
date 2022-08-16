from flask import (
    Blueprint,
    current_app,
    redirect,
    render_template,
    session,
    request,
    url_for,
    flash
)
import datetime
import uuid
from dataclasses import asdict
import re
from passlib.hash import pbkdf2_sha256
import functools
from learning_diary.forms import AddEntryForm, LoginForm, RegisterForm, EditEntryForm
from learning_diary.models import Entry, User


pages = Blueprint(
    "pages", __name__, template_folder="templates", static_folder="static"
)


def login_required(route):
    @functools.wraps(route)
    def route_wrapper(*args, **kwargs):
        if session.get("email") is None:
            return redirect(url_for(".login"))

        return route(*args, **kwargs)

    return route_wrapper


@pages.context_processor
# This function takes one paratemer which is a date. Thanks to the datetime module we can add days to a date and obtain the corresponding date. We create a list comprehension, that stores the selected_date + 3 days before + 3 days after. We then add this function to the context_processon, so that we dont need to import anything.
# >>> index.html
# >>> index()
def add_calc_date_range():
    def date_range(start: datetime.datetime):
        dates = [start + datetime.timedelta(days=diff)
                 for diff in range(-3, 4)]
        return dates
    return {"date_range": date_range}


def today_date():
    today = datetime.datetime.today()
    return datetime.datetime(today.year, today.month, today.day)


def pretty_today():
    today = datetime.datetime.today()
    return today.strftime("%d/%m/%Y")


def format_query_date(date):
    d = [i if len(i) > 1
         else "0" + i
         for i in date.split("/")[::-1]]
    return "-".join(map(str, d)).strip("- ") + " 00:00:00"


def divide_tags(tags: str):
    if ";" in tags:
        return list({tag.strip().capitalize() for tag in tags.split(";") if tag.strip()})
    return list(tags.strip().capitalize())


def format_tags(tags: str):
    tags = str(tags)
    format_str = tags.strip("[]").replace("'", "")
    return ";".join(map(str, [i.strip() for i in format_str.split(",")])).lstrip(";")


def format_title(title: str):
    title = title.strip()
    first_letter_upper = title[0].upper()
    return first_letter_upper + title[1:]


def get_date(date):
    d = [int(i) for i in str(date).split()[0].split("-")]
    return datetime.date(d[0], d[1], d[2]).strftime("%d/%m/%Y")


def prettier_date(date):
    d = [int(i.lstrip("0")) for i in date.split()[0].split("-")]
    d1 = datetime.date(d[0], d[1], d[2]).strftime("%A %d %B %Y")
    d2 = [i.lstrip("0") for i in d1.split()]
    return " ".join(map(str, d2)).strip()


@ pages.get("/toggle-theme")
# Function for the dark-mode
# In the session we store a value called theme, which can be modified when clicking on a button. This action triggers the change in the HTML root
# >>> layout.html -> macros/header.html
# >>> css/main.css
def toggle_theme():
    current_theme = session.get("theme")
    if current_theme == "dark":
        session["theme"] = "light"
    else:
        session["theme"] = "dark"
    return redirect(request.args.get("current_page"))


@pages.route("/add/<string:date>", methods=['GET', 'POST'])
@login_required
def add(date):
    form = AddEntryForm()
    if form.validate_on_submit():
        entry = Entry(
            _id=uuid.uuid4().hex,
            date=get_date(date),
            title=format_title(form.title.data),
            description=form.description.data.strip(),
            tag=divide_tags(form.tag.data)
        )
        current_app.db.entry.insert_one(asdict(entry))
        current_app.db.user.update_one(
            {"_id": session["user_id"]}, {"$push": {"entries": entry._id}}
        )
        return redirect(url_for('pages.index', date=date))
    return render_template('add.html', date=prettier_date(date), form=form)


@pages.route("/edit/<string:_id>", methods=['GET', 'POST'])
@login_required
def edit(_id: str):
    entry = Entry(**current_app.db.entry.find_one({"_id": _id}))
    t = format_tags(entry.tag)
    entry.tag = t
    form = EditEntryForm(obj=entry)
    if form.validate_on_submit():
        entry.title = format_title(form.title.data)
        entry.description = form.description.data.strip()
        entry.tag = divide_tags(form.tag.data)
        current_app.db.entry.update_one(
            {"_id": _id}, {"$set": asdict(entry)}
        )
        return redirect(url_for('pages.index', date=format_query_date(entry.date)))
    return render_template('edit.html', entry=entry, form=form)


@pages.get("/delete/<string:_id>")
@login_required
def delete(_id: str):
    entry_date = Entry(**current_app.db.entry.find_one({"_id": _id})).date
    current_app.db.entry.delete_one({"_id": _id})
    return redirect(url_for(".index", date=format_query_date(entry_date)))


@ pages.route("/", methods=['GET', 'POST'])
@ login_required
def index():
    date_str = request.args.get("date")
    if date_str:
        # Creates a date object starting from a string
        selected_date = datetime.datetime.fromisoformat(date_str)
    else:
        selected_date = today_date()
# This is linked with the date_range function and index.html. By changing the date parameter, the date_str changes, therefore, the selected date changes as well. With the change of the selected_date, we call the date_range function, which creates a new dates range and then it's displayed differently by the html file
    user_data = current_app.db.user.find_one({"email": session["email"]})
    user = User(**user_data)
    entries_data = current_app.db.entry.find({"_id": {"$in": user.entries}})
    displayed_entries = [Entry(**entry)
                         for entry in entries_data
                         if entry["date"] == get_date(selected_date)]
    return render_template(
        "index.html",
        current_year=datetime.datetime.today().year,
        selected_date=selected_date,
        today=pretty_today(),
        entries=displayed_entries
    )


@ pages.route("/register", methods=["GET", "POST"])
def register():
    if session.get("email"):
        return redirect(url_for(".index"))
    # Thi means that the user is already logged in
    form = RegisterForm()
    if form.validate_on_submit():
        user = User(
            _id=uuid.uuid4().hex,
            email=form.email.data,
            password=pbkdf2_sha256.hash(form.password.data)
        )
        current_app.db.user.insert_one(asdict(user))
        flash("User registered succesfully", "Success")
        return redirect(url_for(".login"))
    return render_template(
        "register.html",
        title="Learning Diary - Register",
        form=form
    )


@ pages.route("/login", methods=["GET", "POST"])
def login():
    if session.get("email"):
        return redirect(url_for(".index"))

    form = LoginForm()

    if form.validate_on_submit():
        user_data = current_app.db.user.find_one({"email": form.email.data})
        if not user_data:
            flash("Login credentials not correct", category="danger")
            return redirect(url_for(".login"))
        user = User(**user_data)

        if user and pbkdf2_sha256.verify(form.password.data, user.password):
            session["user_id"] = user._id
            session["email"] = user.email

            return redirect(url_for(".index"))

        flash("Login credentials not correct", category="danger")

    return render_template("login.html", title="Learning Diary - Login", form=form)


@ pages.route("/logout")
@ login_required
def logout():
    current_theme = session.get("theme")
    session.clear()
    session["theme"] = current_theme
    return redirect(url_for(".login"))
