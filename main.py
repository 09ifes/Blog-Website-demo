import werkzeug
from flask import Flask, render_template, request, redirect, url_for
import requests
import smtplib
from flask_wtf import FlaskForm
from werkzeug.security import generate_password_hash, check_password_hash
from wtforms import *
from wtforms.validators import *
import os
import sqlite3
from flask_ckeditor import CKEditor
import datetime
import flask_login
from flask_login import LoginManager, UserMixin


app = Flask(__name__)


SECRET_KEY = os.urandom(32)
my_email = os.environ['MY_EMAIL']
password1 = os.environ['MY_PASSWORD']
app.config['SECRET_KEY'] = SECRET_KEY


ckeditor = CKEditor(app)


login_manager = LoginManager()
login_manager.init_app(app)

all_posts = []
is_authenticated = False


class User(UserMixin):
    id = 0


@login_manager.user_loader
def load_user(user_id):
    user = User()
    return user


def current_date():
    day = datetime.date.today().day
    month = datetime.datetime.strptime(f'{datetime.date.today().month}', "%m").strftime("%B")
    year = datetime.date.today().year
    return f'{month} {day}, {year}'

# use data from db to create json formatted data
def json_convert(db_data):
    parameters = ['id', 'title', 'subtitle', 'body', 'author', 'image_url', 'date']
    data = {}
    index = 0
    for n in db_data:
        data[f'{parameters[index]}'] = n
        index += 1
    return data


def unique_id(database, table):
    # unique id >> highest value id + 1
    blog_id = 0
    all_ids = []
    db = sqlite3.connect(database)
    cursor = db.cursor()
    db_data = cursor.execute(f"SELECT id FROM {table} ").fetchall()
    for n in db_data:
        all_ids.append(n[0])
    for n in all_ids:
        if n > blog_id:
            blog_id = n
    blog_id += 1
    return blog_id


def hash_password(password):
    return generate_password_hash(password, method='pbkdf2:sha256', salt_length=8)


def create_table():
    db = sqlite3.connect("blog-posts.db")
    cursor = db.cursor()
    cursor.execute("CREATE TABLE users(id INTEGER PRIMARY KEY, name varchar(250) NOT NULL,"
                    " email varchar(250) NOT NULL, password varchar(250) NOT NULL)")


class LoginForm(FlaskForm):
    email = StringField(label='Email', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired(message='This field is required')])
    name = StringField(label='Name', validators=[DataRequired()])
    submit = SubmitField(label='Submit')


class BlogForm(FlaskForm):
    title = StringField(label='Title', validators=[DataRequired()])
    subtitle = StringField(label='Subtitle', validators=[DataRequired()])
    author = StringField(label='Author', validators=[DataRequired()])
    img_url = StringField(label='Blog Image URL', validators=[DataRequired()])
    submit = SubmitField()

user = User()
#create_table()

@app.route('/')
def home():
    global all_posts, is_authenticated
    all_posts = []
    db = sqlite3.connect("blog-posts.db")
    cursor = db.cursor()
    all_data = cursor.execute("SELECT id, title, subtitle, body, author, image_url, date FROM blogs").fetchall()
    for n in all_data:
        blog_post = json_convert(n)
        all_posts.append(blog_post)
    return render_template("index.html", posts=all_posts, is_authenticated=is_authenticated)


@app.route('/login', methods=["GET","POST"])
def login():
    global is_authenticated
    incorrect_details = False
    login_form = LoginForm()
    email = login_form.email.data
    password = login_form.password.data
    if request.method == 'POST':
        db = sqlite3.connect("blog-posts.db")
        cursor = db.cursor()
        data = cursor.execute(f"SELECT id, password FROM users WHERE email='{email}'").fetchone()
        if data is None:
            incorrect_details = True
            return render_template('login.html', form=login_form, error=incorrect_details, is_authenticated=is_authenticated)
        else:
            user_password = data[1]
            if check_password_hash(user_password, password):
                user.id = data[0]
                is_authenticated = user.is_authenticated
                flask_login.login_user(user)
                return redirect("/")
            else:
                incorrect_details = True
                return render_template('login.html', form=login_form, error=incorrect_details, is_authenticated=is_authenticated)

    return render_template('login.html', form=login_form, is_authenticated=is_authenticated)


@app.route('/logout')
def logout():
    global is_authenticated
    flask_login.logout_user()
    is_authenticated = False
    return redirect('/')


@app.route('/register', methods=['GET','POST'])
def register():
    global is_authenticated
    email_exists = False
    register_form = LoginForm()

    if request.method == 'POST':
       password = request.form.get('password')
       secure_password = hash_password(password)
       db = sqlite3.connect("blog-posts.db")
       cursor = db.cursor()
       try:
           cursor.execute(
                f"INSERT INTO users VALUES({unique_id('blog-posts.db', 'users')}, '{request.form.get('name')}',"
                f" '{request.form.get('email')}', '{secure_password}')")
           db.commit()
       except sqlite3.IntegrityError as e:
           email_exists = True
           return render_template('register.html', form=register_form, error=email_exists, is_authenticated=is_authenticated)

       db = sqlite3.connect("blog-posts.db")
       cursor = db.cursor()
       data = cursor.execute(f"SELECT id, password FROM users WHERE email='{request.form.get('email')}'").fetchone()
       user.id = data[0]
       is_authenticated = user.is_authenticated
       flask_login.login_user(user)

       return redirect("/")
    else:
        return render_template('register.html', form=register_form, error=email_exists, is_authenticated=is_authenticated)


@app.route('/about')
def about():
    global is_authenticated
    return render_template('about.html', is_authenticated=is_authenticated)


@app.route('/contact', methods=["GET","POST"])
def contact():
    global is_authenticated
    if request.method == "POST":
        name = request.form['name']
        email1 = request.form['email']
        phone = request.form['phone']
        message = request.form['message']
        # code below sends email
        with smtplib.SMTP('smtp-mail.outlook.com') as connection:
            connection.starttls()
            connection.login(user=my_email, password=password1)
            connection.sendmail(from_addr=my_email, to_addrs=f'{email1}',
                                msg=f"subject:Support\n\nName: {name}\nEmail: {email1}\nPhone: {phone}\nMessage: {message}")
        return render_template('contact2.html', is_authenticated=is_authenticated)

    return render_template('contact.html', is_authenticated=is_authenticated)


@app.route('/new-post', methods=["GET","POST"])
@flask_login.login_required
def create_post():
    global is_authenticated
    blog_form = BlogForm()
    if request.method == "POST":
        db = sqlite3.connect("blog-posts.db")
        cursor = db.cursor()
        cursor.execute(
            f"INSERT INTO blogs VALUES({unique_id('blog-posts.db', 'blogs')}, '{blog_form.title.data}', '{blog_form.subtitle.data}',"
            f" '{request.form.get('body')}','{blog_form.author.data}', '{blog_form.img_url.data}', '{current_date()}')")
        db.commit()
        return redirect('/')
    return render_template('new_post.html', form=blog_form, is_authenticated=is_authenticated)


@app.route('/post/<int:number>')
def show_post(number):
    global is_authenticated
    return render_template('post.html', posts=all_posts, n=number, is_authenticated=is_authenticated)


@app.route('/edit-post/<int:post_id>', methods=["GET","POST"])
@flask_login.login_required
def edit_post(post_id):
    global is_authenticated
    blog_form = BlogForm()
    blog_post = all_posts[post_id - 1]
    if request.method == "POST":
        db = sqlite3.connect("blog-posts.db")
        cursor = db.cursor()
        cursor.execute(f"UPDATE blogs SET title='{blog_form.title.data}', subtitle='{blog_form.subtitle.data}',"
                       f" body='{request.form.get('body')}', author='{blog_form.author.data}', image_url='{blog_form.img_url.data}' WHERE id={post_id}")
        db.commit()
        return redirect('/')

    return render_template('edit_post.html', form=blog_form, post=blog_post, number=post_id, is_authenticated=is_authenticated)


@app.route('/delete')
def delete_post():
    post_id = request.args.get('number')
    db = sqlite3.connect("blog-posts.db")
    cursor = db.cursor()
    try:
        cursor.execute(f"DELETE FROM blogs WHERE id={post_id}")
    except sqlite3.OperationalError:
        pass
    db.commit()
    return redirect('/')


if __name__ == "__main__":
    app.run()
