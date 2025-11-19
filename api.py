from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from flask_restful import Resource, Api, reqparse, fields, marshal_with, abort
from flask_cors import CORS
from flask_restx import fields

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://bsuadmin:s0SaTdPKCgGOBkSpXrK4U4qqMXGCISfH@dpg-d444a72dbo4c73b8i87g-a.singapore-postgres.render.com/bsu_map_db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
api = Api(app)
CORS(app)

# ===============================
# REQUEST ARGUMENTS
# ===============================
rooms_args = reqparse.RequestParser()
rooms_args.add_argument('name', type=str, required=True)
rooms_args.add_argument('tag', type=str, required=True)
rooms_args.add_argument('parent', type=str, required=True)
rooms_args.add_argument('type', type=str, required=True)

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
    __tablename__ = 'rooms'
    id = db.Column(db.Integer, primary_key=True)
    tag = db.Column(db.String(60), unique=True, nullable=False)
    name = db.Column(db.String(80), unique=True, nullable=False)
    parent = db.Column(db.String(60), nullable=False)
    type = db.Column(db.String(60), nullable=False)

    schedules = db.relationship(
        'ScheduleModel',
        backref='room',
        lazy=True,
        cascade="all, delete-orphan"
    )

class ScheduleModel(db.Model):
    __tablename__ = 'schedules'
    id = db.Column(db.Integer, primary_key=True)
    day = db.Column(db.String(10), nullable=False)
    start = db.Column(db.String(10), nullable=False)
    end = db.Column(db.String(10), nullable=False)
    subject = db.Column(db.String(100), nullable=False)
    section = db.Column(db.String(20), nullable=False)
    teacher = db.Column(db.String(60), nullable=False)

    room_tag = db.Column(db.String(60), db.ForeignKey('rooms.tag'), nullable=False)

# ===============================
# JSON OUTPUT FIELDS
# ===============================
roomfields = {
    'id': fields.Integer,
    'tag': fields.String,
    'name': fields.String,
    'parent': fields.String,
    'type': fields.String,
}

schedfields = {
    'id': fields.Integer,
    'day': fields.String,
    'start': fields.String,
    'end': fields.String,
    'subject': fields.String,
    'section': fields.String,
    'teacher': fields.String,
    'room_tag': fields.String,
}

# ===============================
# ROOM API
# ===============================
class Rooms(Resource):
    @marshal_with(roomfields)
    def get(self):
        return RoomsModel.query.all()

    @marshal_with(roomfields)
    def post(self):
        name = request.form.get("name")
        tag = request.form.get("tag")
        parent = request.form.get("parent")
        type_ = request.form.get("type")

        room = RoomsModel(name=name, tag=tag, parent=parent, type=type_)
        db.session.add(room)
        db.session.commit()
        return room, 201

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

        if name: room.name = name
        if tag: room.tag = tag
        if parent: room.parent = parent
        if type_: room.type = type_

        db.session.commit()
        return room

    @marshal_with(roomfields)
    def delete(self, id):
        room = RoomsModel.query.filter_by(id=id).first()
        if not room:
            abort(404, "Room not found")
        db.session.delete(room)
        db.session.commit()
        return room, 204

# ===============================
# SCHEDULE API
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
                    room_tag=room_tag
                )
                db.session.add(new_sched)
                inserted.append(new_sched)

        db.session.commit()
        return inserted, 201

class Schedule(Resource):
    @marshal_with(schedfields)
    def delete(self, id):
        schedule = ScheduleModel.query.filter_by(id=id).first()
        if not schedule:
            abort(404, "Schedule not found")
        db.session.delete(schedule)
        db.session.commit()
        return {"message": f"Schedule {id} deleted"}, 204

# ===============================
# ROOM SCHEDULE LOOKUP
# ===============================
class RoomScheds(Resource):
    @marshal_with(schedfields)
    def get(self, room_tag):
        schedules = ScheduleModel.query.filter_by(room_tag=room_tag).all()
        if not schedules:
            abort(404, "Schedule not found")

        # --- HELPER: DAY ORDER ---
        day_order = {
            "monday": 1, "tuesday": 2, "wednesday": 3, 
            "thursday": 4, "friday": 5, "saturday": 6, "sunday": 7
        }

        # --- HELPER: ROBUST TIME PARSER ---
        def parse_time(time_str):
            if not time_str:
                return datetime.min.time() # Handle empty strings
            
            # 1. Clean the string: remove spaces at ends, make uppercase
            # This turns "  7:30 am " into "7:30 AM"
            clean_time = time_str.strip().upper()
            
            # 2. Try different formats to prevent crashing/scrambling
            formats_to_try = [
                "%I:%M %p",  # "07:30 AM" or "7:30 AM" (Standard)
                "%I:%M%p",   # "7:30AM" (No space)
                "%H:%M",     # "14:30" (24-hour format)
                "%H:%M:%S"   # "14:30:00" (Database timestamp format)
            ]

            for fmt in formats_to_try:
                try:
                    return datetime.strptime(clean_time, fmt).time()
                except ValueError:
                    continue
            
            # 3. If all fails, return a default late time so it sits at the bottom
            # rather than scrambling the top of the list.
            return datetime.max.time()

        # --- SORTING LOGIC ---
        # Sort key returns a tuple: (Day Rank, Time Object)
        schedules.sort(key=lambda s: (
            day_order.get(s.day.lower().strip(), 99), # Sort by Day
            parse_time(s.start)                       # Then Sort by Time
        ))

        return schedules

    # ... (Keep your delete and patch methods exactly as they were) ...
    @marshal_with(schedfields)
    def delete(self, id):
        schedule = ScheduleModel.query.filter_by(id=id).first()
        if not schedule:
            abort(404, "Schedule not found")
        db.session.delete(schedule)
        db.session.commit()
        return schedule, 204

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

        db.session.commit()
        return schedule

# ===============================
# FRONTEND AUTH ROUTES
# ===============================
app.secret_key = "supersecretkey"

@app.route("/")
def root_redirect():
    return redirect(url_for("login_page"))

@app.route("/login", methods=["GET", "POST"])
def login_page():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

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
api.add_resource(Rooms, '/api/v1/rooms/')
api.add_resource(Room, '/api/v1/rooms/<int:id>')
api.add_resource(Schedules, '/api/v1/schedules/')
api.add_resource(Schedule, '/api/v1/schedules/<int:id>')
api.add_resource(RoomScheds, '/api/v1/schedules/<string:room_tag>')

@app.route("/rooms")
def rooms_page():
    return render_template("room.html")

@app.route("/schedule")
def schedule_page():
    return render_template("schedule.html")

if __name__ == '__main__':
    app.run(debug=True, host="0.0.0.0", port=5000)
