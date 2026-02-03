# api.py
import os
from datetime import datetime

from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from flask_restful import Resource, Api, reqparse, fields, marshal_with, abort
from flask_cors import CORS
from flask_migrate import Migrate

# ===============================
# APP CONFIG
# ===============================
app = Flask(__name__)

# ===============================
# DATABASE CONFIG (Render-safe)
# - Use DATABASE_URL from environment
# - Force sslmode=require
# - Add robust pool settings for Render Postgres
# ===============================
database_url = os.getenv("DATABASE_URL")

if not database_url:
    raise RuntimeError("DATABASE_URL env var is not set. Add it in Render → Environment.")

# Ensure sslmode=require exists
if "sslmode=" not in database_url:
    sep = "&" if "?" in database_url else "?"
    database_url = f"{database_url}{sep}sslmode=require"

app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_pre_ping": True,            # avoid dead connections
    "pool_recycle": 600,              # recycle often to avoid idle-kill
    "pool_size": 5,
    "max_overflow": 5,
    "pool_timeout": 30,
    "connect_args": {"sslmode": "require"},  # extra safety
}

# Secret key (keep yours if you want)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "supersecretkey")

db = SQLAlchemy(app)
migrate = Migrate(app, db)
api = Api(app)
CORS(app)

# ===============================
# REQUEST ARGUMENTS
# ===============================
rooms_args = reqparse.RequestParser()
rooms_args.add_argument("name", type=str, required=True)
rooms_args.add_argument("tag", type=str, required=True)
rooms_args.add_argument("parent", type=str, required=True)
rooms_args.add_argument("type", type=str, required=True)

sched_args = reqparse.RequestParser()
sched_args.add_argument("day", type=str, required=True)
sched_args.add_argument("start", type=str, required=True)
sched_args.add_argument("end", type=str, required=True)
sched_args.add_argument("subject", type=str, required=True)
sched_args.add_argument("section", type=str, required=True)
sched_args.add_argument("teacher", type=str, required=True)

# ===============================
# MODELS
# ===============================
class RoomsModel(db.Model):
    __tablename__ = "rooms"
    id = db.Column(db.Integer, primary_key=True)
    tag = db.Column(db.String(60), unique=True, nullable=False)
    name = db.Column(db.String(80), unique=True, nullable=False)
    parent = db.Column(db.String(60), nullable=False)
    type = db.Column(db.String(60), nullable=False)

    schedules = db.relationship(
        "ScheduleModel",
        backref="room",
        lazy=True,
        cascade="all, delete-orphan",
    )


class ScheduleModel(db.Model):
    __tablename__ = "schedules"
    id = db.Column(db.Integer, primary_key=True)
    day = db.Column(db.String(10), nullable=False)
    start = db.Column(db.String(10), nullable=False)
    end = db.Column(db.String(10), nullable=False)
    subject = db.Column(db.String(100), nullable=False)
    section = db.Column(db.String(20), nullable=False)
    teacher = db.Column(db.String(60), nullable=False)

    room_tag = db.Column(db.String(60), db.ForeignKey("rooms.tag"), nullable=False)

# ===============================
# JSON OUTPUT FIELDS
# ===============================
roomfields = {
    "id": fields.Integer,
    "tag": fields.String,
    "name": fields.String,
    "parent": fields.String,
    "type": fields.String,
}

schedfields = {
    "id": fields.Integer,
    "day": fields.String,
    "start": fields.String,
    "end": fields.String,
    "subject": fields.String,
    "section": fields.String,
    "teacher": fields.String,
    "room_tag": fields.String,
}

# ===============================
# ROOM API (PLURAL)
# ===============================
class Rooms(Resource):
    @marshal_with(roomfields)
    def get(self):
        exclude_type = request.args.get("exclude")
        filter_type = request.args.get("type")

        query = RoomsModel.query
        if exclude_type:
            query = query.filter(RoomsModel.type != exclude_type)
        if filter_type:
            query = query.filter_by(type=filter_type)

        return query.all()

    @marshal_with(roomfields)
    def post(self):
        name = request.form.get("name")
        tag = request.form.get("tag")
        parent = request.form.get("parent")
        type_ = request.form.get("type")

        room = RoomsModel(name=name, tag=tag, parent=parent, type=type_)
        db.session.add(room)

        # safer commit on flaky connections
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise

        return room, 201

# ===============================
# ROOM API (SINGULAR)
# ===============================
class Room(Resource):
    @marshal_with(roomfields)
    def get(self, id):
        room = RoomsModel.query.filter_by(id=id).first()
        if not room:
            abort(404, "Room not found")
        return room

    @marshal_with(roomfields)
    def patch(self, id):
        room = RoomsModel.query.filter_by(id=id).first()
        if not room:
            abort(404, "Room not found")

        name = request.form.get("name")
        tag = request.form.get("tag")
        parent = request.form.get("parent")
        type_ = request.form.get("type")

        if name:
            room.name = name
        if tag:
            room.tag = tag
        if parent:
            room.parent = parent
        if type_:
            room.type = type_

        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise

        return room

    @marshal_with(roomfields)
    def delete(self, id):
        room = RoomsModel.query.filter_by(id=id).first()
        if not room:
            abort(404, "Room not found")

        db.session.delete(room)
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise

        return room, 204

# ===============================
# SCHEDULE API (LIST / CREATE)
# ===============================
class Schedules(Resource):
    @marshal_with(schedfields)
    def get(self):
        return ScheduleModel.query.all()

    @marshal_with(schedfields)
    def post(self):
        data = request.get_json(force=True)
        inserted = []

        for room_tag, sched_list in data.items():
            for s in sched_list:
                new_sched = ScheduleModel(
                    day=s["day"],
                    start=s["start"],
                    end=s["end"],
                    subject=s["subject"],
                    section=s["section"],
                    teacher=s["teacher"],
                    room_tag=room_tag,
                )
                db.session.add(new_sched)
                inserted.append(new_sched)

        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise

        return inserted, 201

# ===============================
# SCHEDULE API (SINGLE ITEM ACTION)
# ===============================
class Schedule(Resource):
    @marshal_with(schedfields)
    def delete(self, id):
        schedule = ScheduleModel.query.filter_by(id=id).first()
        if not schedule:
            abort(404, "Schedule not found")

        db.session.delete(schedule)
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise

        return {"message": f"Schedule {id} deleted"}, 204

    @marshal_with(schedfields)
    def patch(self, id):
        args = sched_args.parse_args()
        schedule = ScheduleModel.query.filter_by(id=id).first()
        if not schedule:
            abort(404, "Schedule not found")

        schedule.day = args["day"]
        schedule.start = args["start"]
        schedule.end = args["end"]
        schedule.subject = args["subject"]
        schedule.section = args["section"]
        schedule.teacher = args["teacher"]

        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise

        return schedule

# ===============================
# ROOM SCHEDULE LOOKUP (VIEW ONLY)
# ===============================
class RoomScheds(Resource):
    @marshal_with(schedfields)
    def get(self, room_tag):
        schedules = ScheduleModel.query.filter_by(room_tag=room_tag).all()
        if not schedules:
            abort(404, "Schedule not found")

        day_order = {
            "mon": 1, "tue": 2, "wed": 3, "thu": 4,
            "fri": 5, "sat": 6, "sun": 7,
        }

        def get_sort_key(s):
            try:
                d_str = str(s.day).strip().lower()[:3]
                day_val = day_order.get(d_str, 99)

                t_str = str(s.start).strip().upper()
                try:
                    time_val = datetime.strptime(t_str, "%I:%M %p").time()
                except ValueError:
                    try:
                        time_val = datetime.strptime(t_str, "%H:%M").time()
                    except ValueError:
                        try:
                            time_val = datetime.strptime(t_str, "%I:%M%p").time()
                        except ValueError:
                            time_val = datetime.max.time()

                return (day_val, time_val)
            except Exception:
                return (100, datetime.max.time())

        schedules.sort(key=get_sort_key)
        return schedules

# ===============================
# FRONTEND AUTH ROUTES
# ===============================
@app.route("/")
def root_redirect():
    return redirect(url_for("login_page"))

@app.route("/login", methods=["GET", "POST"])
def login_page():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        # ✅ keep as-is (you can move to env vars later)
        if username == "admin" and password == "p4ssw0rd":
            session["logged_in"] = True
            return redirect(url_for("home_page"))
        else:
            return render_template("login.html", error="Invalid username or password")

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop("logged_in", None)
    return redirect(url_for("login_page"))

@app.route("/home")
def home_page():
    if not session.get("logged_in"):
        return redirect(url_for("login_page"))
    return render_template("home.html")

@app.before_request
def require_login():
    allowed_routes = ["login_page", "static", "root_redirect"]
    if request.path.startswith("/api/"):
        return
    if request.endpoint in allowed_routes:
        return
    if not session.get("logged_in"):
        return redirect(url_for("login_page"))

# ===============================
# ROUTE REGISTRATION
# ===============================
api.add_resource(Rooms, "/api/v1/rooms/")
api.add_resource(Room, "/api/v1/rooms/<int:id>")
api.add_resource(Schedules, "/api/v1/schedules/")
api.add_resource(Schedule, "/api/v1/schedules/<int:id>")
api.add_resource(RoomScheds, "/api/v1/schedules/<string:room_tag>")

@app.route("/rooms")
def rooms_page():
    return render_template("room.html")

@app.route("/schedule")
def schedule_page():
    return render_template("schedule.html")

# ===============================
# ENTRYPOINT
# ===============================
if __name__ == "__main__":
    # Local dev only. On Render, use gunicorn:
    # gunicorn api:app
    app.run(debug=True, host="0.0.0.0", port=int(os.getenv("PORT", "5000")))
