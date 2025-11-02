from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from flask_restful import Resource, Api, reqparse, fields, marshal_with, abort
from flask_cors import CORS
from flask_restx import fields


app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
db = SQLAlchemy(app)
api = Api(app)
CORS(app)


# Define request arguements for Room
rooms_args = reqparse.RequestParser()
rooms_args.add_argument('name', type=str,  required=True, help="Name cannot be blank") # defining that name input when creating room data for the database
rooms_args.add_argument('tag', type=str,  required=True, help="Tag cannot be blank") # defining that tag input when creating room data for the database
rooms_args.add_argument('parent', type=str,  required=True, help="Building cannot be blank") # defining that parent input when creating room data for the database
rooms_args.add_argument('type', type=str,  required=True, help="Type cannot be blank") # defining that type input when creating room data for the database

# Define request arguements for Schedule
sched_args = reqparse.RequestParser()
sched_args.add_argument("day", type=str, required=True, help="Day cannot be blank")
sched_args.add_argument("start", type=str, required=True, help="Start cannot be blank")
sched_args.add_argument("end", type=str, required=True, help="End cannot be blank")
sched_args.add_argument("subject", type=str, required=True, help="Subject cannot be blank")
sched_args.add_argument("section", type=str, required=True, help="Section cannot be blank")
sched_args.add_argument("teacher", type=str, required=True, help="Teacher cannot be blank")



# Model Class
class RoomsModel(db.Model):
    __tablename__ = 'rooms'
    id = db.Column(db.Integer, primary_key=True)
    tag = db.Column(db.String(60), nullable=False)
    name = db.Column(db.String(80), unique=True, nullable=False)
    parent = db.Column(db.String(60), nullable=False)
    type = db.Column(db.String(60), nullable=False)

    
    schedules = db.relationship(
        'ScheduleModel',
        backref='room',
        lazy=True,
        cascade="all, delete-orphan"
    )

    #TODO: to be modified if needed
    def __repr__(self):
        return f"<Room {self.name}>"

class ScheduleModel(db.Model):
    __tablename__ = 'schedules'
    id = db.Column(db.Integer, primary_key=True)
    day = db.Column(db.String(10), nullable=False)
    start = db.Column(db.String(10), nullable=False)
    end = db.Column(db.String(10), nullable=False)
    subject = db.Column(db.String(100), nullable=False)
    section = db.Column(db.String(20), nullable=False)
    teacher = db.Column(db.String(60), nullable=False)
    
    room_tag = db.Column(db.Integer, db.ForeignKey('rooms.tag'), nullable=False)
    
    #TODO: to be modified if needed
    def __repr__(self):
        return f"<Schedule {self.subject} in {self.day}>"
    
# create a json structure for Rooms
roomfields = {
    'id' : fields.Integer,
    'tag' : fields.String,
    'name' : fields.String,
    'parent': fields.String,
    'type': fields.String,
}

#create a json structure for Schedule
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
    
# Request returns for Rooms
class Rooms(Resource): 
    @marshal_with(roomfields)
    def get(self):
        rooms = RoomsModel.query.all()
        return rooms

    @marshal_with(roomfields)
    def post(self):
        name = request.form.get("name")
        tag = request.form.get("tag")
        parent = request.form.get("parent")
        type_ = request.form.get("type")

        room = RoomsModel(
            name=name,
            tag=tag,
            parent=parent,
            type=type_,
        )
        db.session.add(room)
        db.session.commit()
        return room, 201
    
class Room(Resource):
    @marshal_with(roomfields)
    def get(self, id):
        room = RoomsModel.query.filter_by(id=id).first()
        if not room:
            abort(404, "Room not found") #return 404 error if no room found
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
            abort(404, "Room not found") #return 404 error if no room found
        db.session.delete(room)
        db.session.commit()
        rooms = RoomsModel.query.all()
        return room, 204
    
# Request returns for Schedule
class Schedules(Resource): 
    @marshal_with(schedfields)
    def get(self):
        schedules = ScheduleModel.query.all()
        return schedules

    @marshal_with(schedfields)
    def post(self):
        data = request.get_json(force=True)  # raw JSON object
        schedules_created = []

        for room_tag, sched_list in data.items():
            for sched in sched_list:
                new_sched = ScheduleModel(
                    day=sched["day"],
                    start=sched["start"],
                    end=sched["end"],
                    subject=sched["subject"],
                    section=sched["section"],
                    teacher=sched["teacher"],
                    room_tag=room_tag   # <-- use the key as room_tag
                )
                db.session.add(new_sched)
                schedules_created.append(new_sched)

        db.session.commit()
        return schedules_created, 201
    
# class Schedule(Resource):
    
    

    
class RoomScheds(Resource):
    @marshal_with(schedfields)
    def get(self, room_tag):
        schedules = ScheduleModel.query.filter_by(room_tag=room_tag).all()
        if not schedules:
            abort(404, "Schedule not found") #return 404 error if no schedules found
        return schedules
        
    @marshal_with(schedfields)
    def delete(self, id):
        schedule = ScheduleModel.query.filter_by(id=id).first()
        if not schedule:
            abort(404, "Schedule not found") #return 404 error if no schedule found
        db.session.delete(schedule)
        db.session.commit()
        schedules = ScheduleModel.query.all()
        return schedule, 204
    
    @marshal_with(schedfields)
    def patch(self, id):
        args = sched_args.parse_args()
        schedule = ScheduleModel.query.filter_by(id=id).first()
        if not schedule:
            abort(404, "Schedule not found") #return 404 error if no schedule found
        schedule.day = args["day"]
        schedule.start = args["start"]
        schedule.end = args["end"]
        schedule.subject = args["subject"]
        schedule.section = args["section"]
        schedule.teacher = args["teacher"]
        db.session.commit()
        return schedule
    
app.secret_key = "supersecretkey"  # Needed for session management

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


# Protect pages: require login for specific routes
@app.before_request
def require_login():
    allowed_routes = ["login_page", "static", "root_redirect"]
    if request.path.startswith("/api/"):
        return
    if request.endpoint in allowed_routes:
        return
    if request.endpoint not in allowed_routes and not session.get("logged_in"):
        return redirect(url_for("login_page"))


# REST request api url
api.add_resource(Rooms, '/api/v1/rooms/')
api.add_resource(Room, '/api/v1/rooms/<int:id>')
api.add_resource(Schedules, '/api/v1/schedules/')
api.add_resource(RoomScheds, '/api/v1/schedules/<int:id>')

# @app.route("/home")
# def home_page():
#     return render_template("home.html")

@app.route("/rooms")
def rooms_page():
    return render_template("room.html")

@app.route("/schedule")
def schedule_page():
    return render_template("schedule.html")

if __name__ == '__main__':
    with app.app_context():
        db.create_all()   # delete database.db and uncomment if you want to reset the database
    app.run(debug=True, host="0.0.0.0", port=5000)
