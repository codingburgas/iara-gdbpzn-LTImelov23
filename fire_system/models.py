from datetime import datetime, date, time
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), default='user')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    employee = db.relationship('Employee', backref='user', uselist=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Rank(db.Model):
    __tablename__ = 'ranks'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    abbreviation = db.Column(db.String(10), nullable=False)
    employees = db.relationship('Employee', backref='rank', lazy=True)

class Employee(db.Model):
    __tablename__ = 'employees'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    rank_id = db.Column(db.Integer, db.ForeignKey('ranks.id'), nullable=True)
    phone = db.Column(db.String(20), nullable=True)
    email = db.Column(db.String(120), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    photo = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    team_assignments = db.relationship('TeamAssignment', backref='employee', lazy=True)
    absences = db.relationship('Absence', backref='employee', lazy=True)
    tasks = db.relationship('TaskAssignment', backref='employee', lazy=True)
    team_leader = db.relationship('Team', backref='leader', lazy=True, foreign_keys='Team.leader_id')

    @property
    def full_name(self):
        rank_abbr = f"{self.rank.abbreviation} " if self.rank else ""
        return f"{rank_abbr}{self.first_name} {self.last_name}"

    @property
    def current_status(self):
        active_absence = Absence.query.filter(
            Absence.employee_id == self.id,
            Absence.start_date <= date.today(),
            Absence.end_date >= date.today(),
            Absence.status == 'approved'
        ).first()
        if active_absence:
            return f"in_{active_absence.absence_type}"
        return "available"

class Vehicle(db.Model):
    __tablename__ = 'vehicles'
    id = db.Column(db.Integer, primary_key=True)
    registration = db.Column(db.String(20), unique=True, nullable=False)
    model = db.Column(db.String(100), nullable=False)
    type = db.Column(db.String(50), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    gps_device_id = db.Column(db.String(100), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    team_assignments = db.relationship('TeamAssignment', backref='vehicle', lazy=True)

class Team(db.Model):
    __tablename__ = 'teams'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    shift = db.Column(db.String(20), nullable=False)
    leader_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    assignments = db.relationship('TeamAssignment', backref='team', lazy=True)
    incidents = db.relationship('Incident', backref='team', lazy=True)

    @property
    def member_count(self):
        return TeamAssignment.query.filter_by(team_id=self.id, is_active=True).count()

    @property
    def available_members(self):
        today = date.today()
        assignments = TeamAssignment.query.filter_by(team_id=self.id, is_active=True).all()
        available = []
        for ass in assignments:
            emp = ass.employee
            if emp.is_active and emp.current_status == 'available':
                available.append(emp)
        return available

class TeamAssignment(db.Model):
    __tablename__ = 'team_assignments'
    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey('teams.id'), nullable=False)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    vehicle_id = db.Column(db.Integer, db.ForeignKey('vehicles.id'), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    assigned_at = db.Column(db.DateTime, default=datetime.utcnow)

class Absence(db.Model):
    __tablename__ = 'absences'
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    absence_type = db.Column(db.String(20), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    reason = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), default='pending')
    approved_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

INCIDENT_TYPES = [
    'fire', 'car_accident', 'flood', 'earthquake', 'chemical_spill',
    'gas_leak', 'forest_fire', 'rescue', 'explosion', 'other'
]

INCIDENT_STATUSES = ['reported', 'dispatched', 'on_scene', 'in_progress', 'contained', 'resolved']

class Incident(db.Model):
    __tablename__ = 'incidents'
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False)
    incident_type = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(20), default='reported')
    priority = db.Column(db.String(10), default='normal')
    address = db.Column(db.String(255), nullable=False)
    city = db.Column(db.String(100), nullable=False)
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)
    description = db.Column(db.Text, nullable=True)
    source = db.Column(db.String(50), default='112')
    team_id = db.Column(db.Integer, db.ForeignKey('teams.id'), nullable=True)
    reported_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    resolved_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    tasks = db.relationship('Task', backref='incident', lazy=True)
    chat_messages = db.relationship('ChatMessage', backref='incident', lazy=True)
    resources = db.relationship('ResourceRequest', backref='incident', lazy=True)
    map_markers = db.relationship('MapMarker', backref='incident', lazy=True)

    def generate_code(self):
        prefix = self.incident_type[:3].upper() if self.incident_type else 'INC'
        count = Incident.query.filter(Incident.id != self.id).count() + 1
        return f"{prefix}-{datetime.utcnow().strftime('%Y%m%d')}-{count:04d}"

class IncidentConfirmation(db.Model):
    __tablename__ = 'incident_confirmations'
    id = db.Column(db.Integer, primary_key=True)
    incident_id = db.Column(db.Integer, db.ForeignKey('incidents.id'), nullable=False)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    confirmed_at = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='confirmed')
    notes = db.Column(db.Text, nullable=True)

TASK_CATEGORIES = ['logistics', 'operational', 'administrative', 'other']
TASK_STATUSES = ['pending', 'in_progress', 'completed', 'cancelled']

class Task(db.Model):
    __tablename__ = 'tasks'
    id = db.Column(db.Integer, primary_key=True)
    incident_id = db.Column(db.Integer, db.ForeignKey('incidents.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    category = db.Column(db.String(20), default='operational')
    status = db.Column(db.String(20), default='pending')
    priority = db.Column(db.String(10), default='normal')
    assigned_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    due_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)

    assignments = db.relationship('TaskAssignment', backref='task', lazy=True)

class TaskAssignment(db.Model):
    __tablename__ = 'task_assignments'
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('tasks.id'), nullable=False)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    assigned_at = db.Column(db.DateTime, default=datetime.utcnow)

class ResourceRequest(db.Model):
    __tablename__ = 'resource_requests'
    id = db.Column(db.Integer, primary_key=True)
    incident_id = db.Column(db.Integer, db.ForeignKey('incidents.id'), nullable=False)
    resource_type = db.Column(db.String(100), nullable=False)
    quantity = db.Column(db.String(50), nullable=True)
    description = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), default='pending')
    requested_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    fulfilled_at = db.Column(db.DateTime, nullable=True)

class MapMarker(db.Model):
    __tablename__ = 'map_markers'
    id = db.Column(db.Integer, primary_key=True)
    incident_id = db.Column(db.Integer, db.ForeignKey('incidents.id'), nullable=False)
    marker_type = db.Column(db.String(50), nullable=False)
    label = db.Column(db.String(200), nullable=True)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class ChatMessage(db.Model):
    __tablename__ = 'chat_messages'
    id = db.Column(db.Integer, primary_key=True)
    incident_id = db.Column(db.Integer, db.ForeignKey('incidents.id'), nullable=False)
    sender_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    message_type = db.Column(db.String(20), default='text')
    content = db.Column(db.Text, nullable=True)
    image_url = db.Column(db.String(255), nullable=True)
    is_template = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    sender = db.relationship('Employee', backref='sent_messages')

class ChatTemplate(db.Model):
    __tablename__ = 'chat_templates'
    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(50), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class VideoCall(db.Model):
    __tablename__ = 'video_calls'
    id = db.Column(db.Integer, primary_key=True)
    incident_id = db.Column(db.Integer, db.ForeignKey('incidents.id'), nullable=False)
    initiator_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    room_name = db.Column(db.String(100), unique=True, nullable=False)
    status = db.Column(db.String(20), default='active')
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    ended_at = db.Column(db.DateTime, nullable=True)

class SOSSignal(db.Model):
    __tablename__ = 'sos_signals'
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    incident_id = db.Column(db.Integer, db.ForeignKey('incidents.id'), nullable=True)
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)
    message = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), default='active')
    sent_at = db.Column(db.DateTime, default=datetime.utcnow)
    resolved_at = db.Column(db.DateTime, nullable=True)

    employee = db.relationship('Employee', backref='sos_signals')

class ShiftLog(db.Model):
    __tablename__ = 'shift_logs'
    id = db.Column(db.Integer, primary_key=True)
    shift = db.Column(db.String(20), nullable=False)
    team_id = db.Column(db.Integer, db.ForeignKey('teams.id'), nullable=True)
    started_at = db.Column(db.DateTime, nullable=False)
    ended_at = db.Column(db.DateTime, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
