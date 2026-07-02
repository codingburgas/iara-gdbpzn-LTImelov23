import os
import uuid
import json
from datetime import datetime, date, timedelta
from functools import wraps

from flask import (Flask, render_template, redirect, url_for, request,
                   flash, jsonify, abort, session, send_from_directory)
from flask_login import (LoginManager, login_user, logout_user,
                         login_required, current_user)
from werkzeug.utils import secure_filename
from flask_socketio import SocketIO, emit, join_room, leave_room

from models import db, User, Employee, Rank, Vehicle, Team, TeamAssignment
from models import Absence, Incident, IncidentConfirmation, Task, TaskAssignment
from models import ResourceRequest, MapMarker, ChatMessage, ChatTemplate
from models import VideoCall, SOSSignal, ShiftLog
from forms import (LoginForm, EmployeeForm, TeamForm, VehicleForm,
                   IncidentForm, AbsenceForm, TaskForm, ResourceRequestForm,
                   ChatMessageForm, MapMarkerForm)

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'fire-system-secret-key-2024')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///fire_system.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join('static', 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

db.init_app(app)
socketio = SocketIO(app, cors_allowed_origins='*')
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please login to access this page.'

with app.app_context():
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            abort(403)
        return f(*args, **kwargs)
    return decorated

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.context_processor
def inject_now():
    return {
        'now': datetime.utcnow(),
        'today': date.today(),
        'active_incidents': Incident.query.filter(
            Incident.status.in_(['reported', 'dispatched', 'on_scene', 'in_progress'])
        ).count()
    }

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_upload(file):
    if file and allowed_file(file.filename):
        ext = file.filename.rsplit('.', 1)[1].lower()
        filename = f"{uuid.uuid4().hex}.{ext}"
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        return filename
    return None

# =========== AUTH ===========

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and user.check_password(form.password.data):
            login_user(user)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('dashboard'))
        flash('Invalid username or password.', 'danger')
    return render_template('login.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# =========== DASHBOARD ===========

@app.route('/')
@app.route('/dashboard')
@login_required
def dashboard():
    today_date = date.today()
    active_incidents_list = Incident.query.filter(
        Incident.status.in_(['reported', 'dispatched', 'on_scene', 'in_progress'])
    ).order_by(Incident.created_at.desc()).all()

    recent_incidents = Incident.query.order_by(Incident.created_at.desc()).limit(5).all()
    total_employees = Employee.query.filter_by(is_active=True).count()
    available_employees = 0
    for emp in Employee.query.filter_by(is_active=True).all():
        if emp.current_status == 'available':
            available_employees += 1

    active_teams = Team.query.filter_by(is_active=True).all()
    total_vehicles = Vehicle.query.filter_by(is_active=True).count()
    today_absences_count = Absence.query.filter(
        Absence.start_date <= today_date,
        Absence.end_date >= today_date,
        Absence.status == 'approved'
    ).count()

    status_counts = {}
    for s in ['reported', 'dispatched', 'on_scene', 'in_progress', 'contained', 'resolved']:
        status_counts[s] = Incident.query.filter_by(status=s).count()

    return render_template('dashboard.html',
        active_incidents_list=active_incidents_list,
        recent_incidents=recent_incidents,
        total_employees=total_employees,
        available_employees=available_employees,
        active_teams=active_teams,
        total_vehicles=total_vehicles,
        today_absences_count=today_absences_count,
        status_counts=status_counts)

# =========== EMPLOYEES ===========

@app.route('/employees')
@login_required
def employee_list():
    employees = Employee.query.order_by(Employee.last_name).all()
    return render_template('employees/list.html', employees=employees)

@app.route('/employees/<int:id>')
@login_required
def employee_detail(id):
    employee = Employee.query.get_or_404(id)
    return render_template('employees/detail.html', employee=employee)

@app.route('/employees/create', methods=['GET', 'POST'])
@login_required
@admin_required
def employee_create():
    form = EmployeeForm()
    form.rank_id.choices = [(0, '-- Select Rank --')] + [
        (r.id, f"{r.abbreviation} - {r.name}") for r in Rank.query.all()]
    if form.validate_on_submit():
        photo = save_upload(form.photo.data) if form.photo.data else None
        emp = Employee(
            first_name=form.first_name.data,
            last_name=form.last_name.data,
            rank_id=form.rank_id.data if form.rank_id.data != 0 else None,
            phone=form.phone.data,
            email=form.email.data,
            photo=photo
        )
        db.session.add(emp)
        db.session.commit()
        flash('Employee created successfully.', 'success')
        return redirect(url_for('employee_list'))
    return render_template('employees/form.html', form=form, title='Create Employee')

@app.route('/employees/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def employee_edit(id):
    employee = Employee.query.get_or_404(id)
    form = EmployeeForm(obj=employee)
    form.rank_id.choices = [(0, '-- Select Rank --')] + [
        (r.id, f"{r.abbreviation} - {r.name}") for r in Rank.query.all()]
    if form.validate_on_submit():
        employee.first_name = form.first_name.data
        employee.last_name = form.last_name.data
        employee.rank_id = form.rank_id.data if form.rank_id.data != 0 else None
        employee.phone = form.phone.data
        employee.email = form.email.data
        if form.photo.data:
            photo = save_upload(form.photo.data)
            if photo:
                employee.photo = photo
        db.session.commit()
        flash('Employee updated successfully.', 'success')
        return redirect(url_for('employee_detail', id=employee.id))
    form.first_name.data = employee.first_name
    form.last_name.data = employee.last_name
    form.rank_id.data = employee.rank_id or 0
    form.phone.data = employee.phone
    form.email.data = employee.email
    return render_template('employees/form.html', form=form, title='Edit Employee', employee=employee)

@app.route('/employees/<int:id>/absence', methods=['GET', 'POST'])
@login_required
def employee_absence(id):
    employee = Employee.query.get_or_404(id)
    form = AbsenceForm()
    if form.validate_on_submit():
        absence = Absence(
            employee_id=id,
            absence_type=form.absence_type.data,
            start_date=form.start_date.data,
            end_date=form.end_date.data,
            reason=form.reason.data,
            status='approved',
            approved_by=current_user.id
        )
        db.session.add(absence)
        db.session.commit()
        flash('Absence recorded.', 'success')
        return redirect(url_for('employee_detail', id=id))
    return render_template('employees/absence.html', form=form, employee=employee)

# =========== TEAMS ===========

@app.route('/teams')
@login_required
def team_list():
    teams = Team.query.all()
    return render_template('teams/list.html', teams=teams)

@app.route('/teams/<int:id>')
@login_required
def team_detail(id):
    team = Team.query.get_or_404(id)
    employees = Employee.query.filter_by(is_active=True).all()
    vehicles = Vehicle.query.filter_by(is_active=True).all()
    return render_template('teams/detail.html', team=team, employees=employees, vehicles=vehicles)

@app.route('/teams/create', methods=['GET', 'POST'])
@login_required
@admin_required
def team_create():
    form = TeamForm()
    form.leader_id.choices = [(0, '-- Select Leader --')] + [
        (e.id, e.full_name) for e in Employee.query.filter_by(is_active=True).all()]
    if form.validate_on_submit():
        team = Team(
            name=form.name.data,
            shift=form.shift.data,
            leader_id=form.leader_id.data if form.leader_id.data != 0 else None
        )
        db.session.add(team)
        db.session.commit()
        flash('Team created successfully.', 'success')
        return redirect(url_for('team_list'))
    return render_template('teams/form.html', form=form, title='Create Team')

@app.route('/teams/<int:id>/assign', methods=['POST'])
@login_required
@admin_required
def team_assign(id):
    team = Team.query.get_or_404(id)
    employee_id = request.form.get('employee_id', type=int)
    vehicle_id = request.form.get('vehicle_id', type=int)
    if employee_id:
        existing = TeamAssignment.query.filter_by(
            employee_id=employee_id, team_id=team.id, is_active=True).first()
        if not existing:
            assignment = TeamAssignment(
                team_id=team.id,
                employee_id=employee_id,
                vehicle_id=vehicle_id if vehicle_id else None
            )
            db.session.add(assignment)
            db.session.commit()
            flash('Employee assigned to team.', 'success')
    return redirect(url_for('team_detail', id=team.id))

@app.route('/teams/<int:team_id>/unassign/<int:assignment_id>', methods=['POST'])
@login_required
@admin_required
def team_unassign(team_id, assignment_id):
    assignment = TeamAssignment.query.get_or_404(assignment_id)
    assignment.is_active = False
    db.session.commit()
    flash('Employee removed from team.', 'success')
    return redirect(url_for('team_detail', id=team_id))

# =========== VEHICLES ===========

@app.route('/vehicles')
@login_required
def vehicle_list():
    vehicles = Vehicle.query.all()
    return render_template('vehicles.html', vehicles=vehicles)

@app.route('/vehicles/create', methods=['GET', 'POST'])
@login_required
@admin_required
def vehicle_create():
    form = VehicleForm()
    if form.validate_on_submit():
        vehicle = Vehicle(
            registration=form.registration.data,
            model=form.model.data,
            type=form.type.data,
            gps_device_id=form.gps_device_id.data
        )
        db.session.add(vehicle)
        db.session.commit()
        flash('Vehicle created.', 'success')
        return redirect(url_for('vehicle_list'))
    return render_template('vehicle_form.html', form=form, title='Create Vehicle')

# =========== INCIDENTS ===========

@app.route('/incidents')
@login_required
def incident_list():
    status_filter = request.args.get('status', '')
    query = Incident.query
    if status_filter:
        query = query.filter_by(status=status_filter)
    incidents = query.order_by(Incident.created_at.desc()).all()
    return render_template('incidents/list.html', incidents=incidents, status_filter=status_filter)

@app.route('/incidents/<int:id>')
@login_required
def incident_detail(id):
    incident = Incident.query.get_or_404(id)
    return render_template('incidents/detail.html', incident=incident)

@app.route('/incidents/create', methods=['GET', 'POST'])
@login_required
def incident_create():
    form = IncidentForm()
    form.team_id.choices = [(0, '-- Auto Assign --')] + [
        (t.id, f"{t.name} ({t.shift})") for t in Team.query.filter_by(is_active=True).all()]
    if form.validate_on_submit():
        incident = Incident(
            incident_type=form.incident_type.data,
            priority=form.priority.data,
            address=form.address.data,
            city=form.city.data,
            latitude=form.latitude.data,
            longitude=form.longitude.data,
            description=form.description.data,
            source=form.source.data,
            reported_by=current_user.id
        )
        if form.team_id.data and form.team_id.data != 0:
            incident.team_id = form.team_id.data
        incident.code = incident.generate_code()
        db.session.add(incident)
        db.session.commit()

        if incident.team_id:
            send_notification_to_team(incident)
        flash(f'Incident {incident.code} created.', 'success')
        return redirect(url_for('incident_detail', id=incident.id))
    return render_template('incidents/form.html', form=form, title='Create Incident')

@app.route('/incidents/<int:id>/status', methods=['POST'])
@login_required
def incident_update_status(id):
    incident = Incident.query.get_or_404(id)
    new_status = request.form.get('status')
    if new_status in ['reported', 'dispatched', 'on_scene', 'in_progress', 'contained', 'resolved']:
        incident.status = new_status
        if new_status == 'resolved':
            incident.resolved_at = datetime.utcnow()
        db.session.commit()
        socketio.emit('incident_update', {
            'id': incident.id,
            'code': incident.code,
            'status': incident.status
        }, room=f'incident_{incident.id}')
        flash(f'Status updated to {new_status}.', 'success')
    return redirect(url_for('incident_detail', id=incident.id))

@app.route('/incidents/<int:id>/assign_team', methods=['POST'])
@login_required
@admin_required
def incident_assign_team(id):
    incident = Incident.query.get_or_404(id)
    team_id = request.form.get('team_id', type=int)
    team = Team.query.get(team_id)
    if team:
        incident.team_id = team.id
        incident.status = 'dispatched'
        db.session.commit()
        send_notification_to_team(incident)
        flash(f'Team {team.name} assigned.', 'success')
    return redirect(url_for('incident_detail', id=incident.id))

def send_notification_to_team(incident):
    if incident.team:
        for assignment in incident.team.assignments:
            if assignment.is_active:
                socketio.emit('new_incident', {
                    'id': incident.id,
                    'code': incident.code,
                    'type': incident.incident_type,
                    'address': incident.address,
                    'latitude': incident.latitude,
                    'longitude': incident.longitude
                }, room=f'employee_{assignment.employee_id}')

# =========== TASKS ===========

@app.route('/incidents/<int:incident_id>/tasks')
@login_required
def task_list(incident_id):
    incident = Incident.query.get_or_404(incident_id)
    return render_template('tasks/list.html', incident=incident)

@app.route('/incidents/<int:incident_id>/tasks/create', methods=['GET', 'POST'])
@login_required
def task_create(incident_id):
    incident = Incident.query.get_or_404(incident_id)
    form = TaskForm()
    if form.validate_on_submit():
        task = Task(
            incident_id=incident_id,
            title=form.title.data,
            description=form.description.data,
            category=form.category.data,
            priority=form.priority.data,
            assigned_by=current_user.id,
            due_at=form.due_at.data
        )
        db.session.add(task)
        db.session.commit()

        if form.employee_ids.data:
            for eid_str in form.employee_ids.data.split(','):
                eid = eid_str.strip()
                if eid.isdigit():
                    ta = TaskAssignment(task_id=task.id, employee_id=int(eid))
                    db.session.add(ta)
                    socketio.emit('new_task', {
                        'task_id': task.id,
                        'incident_id': incident_id,
                        'title': task.title
                    }, room=f'employee_{int(eid)}')
        db.session.commit()
        flash('Task created.', 'success')
        return redirect(url_for('task_list', incident_id=incident_id))
    return render_template('tasks/form.html', form=form, incident=incident)

@app.route('/tasks/<int:id>/status', methods=['POST'])
@login_required
def task_update_status(id):
    task = Task.query.get_or_404(id)
    new_status = request.form.get('status')
    if new_status in ['pending', 'in_progress', 'completed', 'cancelled']:
        task.status = new_status
        if new_status == 'completed':
            task.completed_at = datetime.utcnow()
        db.session.commit()
        flash(f'Task status updated.', 'success')
    return redirect(request.referrer or url_for('task_list', incident_id=task.incident_id))

# =========== RESOURCES ===========

@app.route('/incidents/<int:incident_id>/resources')
@login_required
def resource_list(incident_id):
    incident = Incident.query.get_or_404(incident_id)
    return render_template('resources/list.html', incident=incident)

@app.route('/incidents/<int:incident_id>/resources/create', methods=['GET', 'POST'])
@login_required
def resource_create(incident_id):
    incident = Incident.query.get_or_404(incident_id)
    form = ResourceRequestForm()
    if form.validate_on_submit():
        req = ResourceRequest(
            incident_id=incident_id,
            resource_type=form.resource_type.data,
            quantity=form.quantity.data,
            description=form.description.data,
            requested_by=current_user.id
        )
        db.session.add(req)
        db.session.commit()
        flash('Resource request created.', 'success')
        return redirect(url_for('resource_list', incident_id=incident_id))
    return render_template('resources/form.html', form=form, incident=incident)

@app.route('/resources/<int:id>/status', methods=['POST'])
@login_required
def resource_update_status(id):
    req = ResourceRequest.query.get_or_404(id)
    new_status = request.form.get('status')
    if new_status in ['pending', 'approved', 'delivered', 'cancelled']:
        req.status = new_status
        if new_status == 'delivered':
            req.fulfilled_at = datetime.utcnow()
        db.session.commit()
        flash('Resource status updated.', 'success')
    return redirect(request.referrer or url_for('resource_list', incident_id=req.incident_id))

# =========== MAP ===========

@app.route('/incidents/<int:incident_id>/map')
@login_required
def incident_map(incident_id):
    incident = Incident.query.get_or_404(incident_id)
    return render_template('map/view.html', incident=incident)

@app.route('/api/incidents/<int:incident_id>/markers')
@login_required
def get_markers(incident_id):
    markers = MapMarker.query.filter_by(incident_id=incident_id).all()
    return jsonify([{
        'id': m.id,
        'type': m.marker_type,
        'label': m.label,
        'lat': m.latitude,
        'lng': m.longitude,
        'created_at': m.created_at.isoformat()
    } for m in markers])

@app.route('/api/incidents/<int:incident_id>/markers/create', methods=['POST'])
@login_required
def create_marker(incident_id):
    data = request.get_json()
    marker = MapMarker(
        incident_id=incident_id,
        marker_type=data['marker_type'],
        label=data.get('label', ''),
        latitude=data['latitude'],
        longitude=data['longitude'],
        created_by=current_user.id
    )
    db.session.add(marker)
    db.session.commit()

    socketio.emit('new_marker', {
        'id': marker.id,
        'incident_id': incident_id,
        'type': marker.marker_type,
        'label': marker.label,
        'lat': marker.latitude,
        'lng': marker.longitude
    }, room=f'incident_{incident_id}')

    return jsonify({'success': True, 'id': marker.id})

@app.route('/api/incidents/<int:incident_id>/team-locations')
@login_required
def get_team_locations(incident_id):
    incident = Incident.query.get_or_404(incident_id)
    locations = []
    if incident.team:
        for ta in incident.team.assignments:
            if ta.is_active and ta.vehicle and ta.vehicle.gps_device_id:
                locations.append({
                    'employee': ta.employee.full_name,
                    'vehicle': ta.vehicle.registration,
                    'gps_id': ta.vehicle.gps_device_id,
                    'lat': 42.7,
                    'lng': 23.33
                })
    return jsonify(locations)

# =========== CHAT ===========

@app.route('/incidents/<int:incident_id>/chat')
@login_required
def chat_view(incident_id):
    incident = Incident.query.get_or_404(incident_id)
    messages = ChatMessage.query.filter_by(incident_id=incident_id)\
        .order_by(ChatMessage.created_at.asc()).all()
    templates = ChatTemplate.query.all()
    return render_template('chat/view.html', incident=incident,
                          messages=messages, templates=templates)

@app.route('/api/incidents/<int:incident_id>/chat/send', methods=['POST'])
@login_required
def send_chat_message(incident_id):
    content = request.form.get('content', '').strip()
    image_file = request.files.get('image')
    is_template = request.form.get('is_template', 'false') == 'true'

    emp = Employee.query.filter_by(user_id=current_user.id).first()
    if not emp:
        return jsonify({'error': 'Employee not found'}), 404

    image_url = None
    if image_file:
        image_url = save_upload(image_file)

    msg = ChatMessage(
        incident_id=incident_id,
        sender_id=emp.id,
        message_type='image' if image_url else 'text',
        content=content,
        image_url=image_url,
        is_template=is_template
    )
    db.session.add(msg)
    db.session.commit()

    msg_data = {
        'id': msg.id,
        'sender': emp.full_name,
        'sender_id': emp.id,
        'content': msg.content,
        'image_url': f'/static/uploads/{msg.image_url}' if msg.image_url else None,
        'message_type': msg.message_type,
        'created_at': msg.created_at.isoformat()
    }
    socketio.emit('chat_message', msg_data, room=f'incident_{incident_id}')
    return jsonify(msg_data)

@app.route('/api/chat/templates')
@login_required
def get_chat_templates():
    templates = ChatTemplate.query.all()
    return jsonify([{
        'id': t.id,
        'category': t.category,
        'content': t.content
    } for t in templates])

# =========== SOS ===========

@app.route('/sos')
@login_required
def sos_list():
    signals = SOSSignal.query.filter_by(status='active')\
        .order_by(SOSSignal.sent_at.desc()).all()
    return render_template('sos.html', signals=signals)

@app.route('/api/sos/send', methods=['POST'])
@login_required
def send_sos():
    data = request.get_json()
    emp = Employee.query.filter_by(user_id=current_user.id).first()
    if not emp:
        return jsonify({'error': 'Employee not found'}), 404

    signal = SOSSignal(
        employee_id=emp.id,
        incident_id=data.get('incident_id'),
        latitude=data.get('latitude'),
        longitude=data.get('longitude'),
        message=data.get('message', 'EMERGENCY!'),
        status='active'
    )
    db.session.add(signal)
    db.session.commit()

    socketio.emit('sos_alert', {
        'id': signal.id,
        'employee': emp.full_name,
        'lat': signal.latitude,
        'lng': signal.longitude,
        'message': signal.message,
        'time': signal.sent_at.isoformat()
    })
    return jsonify({'success': True, 'id': signal.id})

@app.route('/api/sos/<int:id>/resolve', methods=['POST'])
@login_required
def resolve_sos(id):
    signal = SOSSignal.query.get_or_404(id)
    signal.status = 'resolved'
    signal.resolved_at = datetime.utcnow()
    db.session.commit()
    socketio.emit('sos_resolved', {'id': id})
    return jsonify({'success': True})

# =========== VIDEO CALLS ===========

@app.route('/incidents/<int:incident_id>/video')
@login_required
def video_call(incident_id):
    incident = Incident.query.get_or_404(incident_id)
    room = f"video_{incident_id}_{uuid.uuid4().hex[:8]}"
    emp = Employee.query.filter_by(user_id=current_user.id).first()
    if emp:
        call = VideoCall(
            incident_id=incident_id,
            initiator_id=emp.id,
            room_name=room,
            status='active'
        )
        db.session.add(call)
        db.session.commit()
        socketio.emit('video_call_started', {
            'incident_id': incident_id,
            'room': room,
            'initiator': emp.full_name
        }, room=f'incident_{incident_id}')
    return render_template('video_call.html', incident=incident, room=room)

# =========== ABSENCES ===========

@app.route('/absences')
@login_required
def absence_list():
    today_date = date.today()
    absences = Absence.query.filter(
        Absence.end_date >= today_date
    ).order_by(Absence.start_date.asc()).all()
    return render_template('absences.html', absences=absences)

# =========== SHIFT MANAGEMENT ===========

@app.route('/shifts')
@login_required
def shift_list():
    logs = ShiftLog.query.order_by(ShiftLog.started_at.desc()).limit(20).all()
    teams = Team.query.filter_by(is_active=True).all()
    return render_template('shifts.html', logs=logs, teams=teams)

@app.route('/shifts/start', methods=['POST'])
@login_required
@admin_required
def shift_start():
    shift = request.form.get('shift')
    team_id = request.form.get('team_id', type=int)
    log = ShiftLog(
        shift=shift,
        team_id=team_id,
        started_at=datetime.utcnow(),
        created_by=current_user.id
    )
    db.session.add(log)
    db.session.commit()
    flash(f'Shift started.', 'success')
    return redirect(url_for('shift_list'))

@app.route('/shifts/<int:id>/end', methods=['POST'])
@login_required
@admin_required
def shift_end(id):
    log = ShiftLog.query.get_or_404(id)
    log.ended_at = datetime.utcnow()
    log.notes = request.form.get('notes', '')
    db.session.commit()
    flash('Shift ended.', 'success')
    return redirect(url_for('shift_list'))

# =========== API ===========

@app.route('/api/incidents/active')
@login_required
def api_active_incidents():
    incidents = Incident.query.filter(
        Incident.status.in_(['reported', 'dispatched', 'on_scene', 'in_progress'])
    ).all()
    return jsonify([{
        'id': i.id,
        'code': i.code,
        'type': i.incident_type,
        'status': i.status,
        'address': i.address,
        'city': i.city,
        'lat': i.latitude,
        'lng': i.longitude
    } for i in incidents])

@app.route('/api/employees/available')
@login_required
def api_available_employees():
    available = []
    for emp in Employee.query.filter_by(is_active=True).all():
        if emp.current_status == 'available':
            available.append({
                'id': emp.id,
                'name': emp.full_name,
                'rank': emp.rank.abbreviation if emp.rank else ''
            })
    return jsonify(available)

@app.route('/api/employees/<int:id>/location', methods=['POST'])
@login_required
def api_update_location(id):
    data = request.get_json()
    socketio.emit('location_update', {
        'employee_id': id,
        'lat': data['latitude'],
        'lng': data['longitude']
    })
    return jsonify({'success': True})

@app.route('/api/incidents/<int:id>/confirm', methods=['POST'])
@login_required
def api_confirm_incident(id):
    emp = Employee.query.filter_by(user_id=current_user.id).first()
    if not emp:
        return jsonify({'error': 'Employee not found'}), 404
    confirmation = IncidentConfirmation(
        incident_id=id,
        employee_id=emp.id,
        status='confirmed'
    )
    db.session.add(confirmation)
    db.session.commit()
    socketio.emit('incident_confirmed', {
        'incident_id': id,
        'employee': emp.full_name
    }, room=f'incident_{id}')
    return jsonify({'success': True})

# =========== STATIC FILES ===========

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# =========== SOCKET.IO ===========

@socketio.on('connect')
def handle_connect():
    if current_user.is_authenticated:
        emp = Employee.query.filter_by(user_id=current_user.id).first()
        if emp:
            join_room(f'employee_{emp.id}')

@socketio.on('join_incident')
def handle_join_incident(data):
    join_room(f'incident_{data["incident_id"]}')

@socketio.on('leave_incident')
def handle_leave_incident(data):
    leave_room(f'incident_{data["incident_id"]}')

# =========== SEED DATA ===========

def seed_data():
    if Rank.query.first():
        return

    ranks = [
        Rank(name='Главен комисар', abbreviation='гл. комисар'),
        Rank(name='Комисар', abbreviation='комисар'),
        Rank(name='Главен инспектор', abbreviation='гл. инспектор'),
        Rank(name='Инспектор', abbreviation='инспектор'),
        Rank(name='Старши пожарникар', abbreviation='ст. пожарникар'),
        Rank(name='Пожарникар', abbreviation='пожарникар'),
        Rank(name='Младши пожарникар', abbreviation='мл. пожарникар'),
    ]
    db.session.add_all(ranks)

    admin = User(
        username='admin',
        email='admin@fire.bg',
        role='admin'
    )
    admin.set_password('admin123')
    db.session.add(admin)

    operator = User(
        username='operator',
        email='operator@fire.bg',
        role='user'
    )
    operator.set_password('operator123')
    db.session.add(operator)

    db.session.flush()

    employees_data = [
        {'first': 'Георги', 'last': 'Георгиев', 'rank': 6, 'phone': '0888000001'},
        {'first': 'Иван', 'last': 'Иванов', 'rank': 6, 'phone': '0888000002'},
        {'first': 'Димитър', 'last': 'Димитров', 'rank': 5, 'phone': '0888000003'},
        {'first': 'Петър', 'last': 'Петров', 'rank': 5, 'phone': '0888000004'},
        {'first': 'Николай', 'last': 'Николов', 'rank': 4, 'phone': '0888000005'},
        {'first': 'Александър', 'last': 'Александров', 'rank': 6, 'phone': '0888000006'},
        {'first': 'Стоян', 'last': 'Стоянов', 'rank': 6, 'phone': '0888000007'},
        {'first': 'Христо', 'last': 'Христов', 'rank': 3, 'phone': '0888000008'},
        {'first': 'Мария', 'last': 'Маринова', 'rank': 4, 'phone': '0888000009'},
        {'first': 'Елена', 'last': 'Еленова', 'rank': 6, 'phone': '0888000010'},
    ]
    employees = []
    for ed in employees_data:
        emp = Employee(
            first_name=ed['first'],
            last_name=ed['last'],
            rank_id=ed['rank'],
            phone=ed['phone'],
            is_active=True
        )
        db.session.add(emp)
        employees.append(emp)
    db.session.flush()

    employees[0].user_id = admin.id
    employees[1].user_id = operator.id

    vehicles_data = [
        {'registration': 'CB 0001 PK', 'model': 'Mercedes Atego', 'type': 'fire_engine'},
        {'registration': 'CB 0002 PK', 'model': 'Scania P320', 'type': 'fire_engine'},
        {'registration': 'CB 0003 PK', 'model': 'Iveco Trakker', 'type': 'tanker'},
        {'registration': 'CB 0004 PK', 'model': 'MAN TGM', 'type': 'ladder'},
        {'registration': 'CB 0005 PK', 'model': 'Toyota Land Cruiser', 'type': 'command'},
    ]
    vehicles = []
    for vd in vehicles_data:
        v = Vehicle(**vd, is_active=True)
        db.session.add(v)
        vehicles.append(v)
    db.session.flush()

    team_a = Team(name='Екип Алфа', shift='day', leader_id=employees[2].id)
    team_b = Team(name='Екип Браво', shift='day', leader_id=employees[3].id)
    team_c = Team(name='Екип Чарли', shift='night', leader_id=employees[4].id)
    db.session.add_all([team_a, team_b, team_c])
    db.session.flush()

    assignments = [
        (team_a.id, employees[0].id, vehicles[0].id),
        (team_a.id, employees[2].id, vehicles[0].id),
        (team_a.id, employees[5].id, vehicles[0].id),
        (team_b.id, employees[1].id, vehicles[1].id),
        (team_b.id, employees[3].id, vehicles[1].id),
        (team_b.id, employees[6].id, vehicles[1].id),
        (team_c.id, employees[4].id, vehicles[2].id),
        (team_c.id, employees[7].id, vehicles[2].id),
        (team_c.id, employees[8].id, vehicles[2].id),
    ]
    for tid, eid, vid in assignments:
        db.session.add(TeamAssignment(team_id=tid, employee_id=eid, vehicle_id=vid))

    templates_data = [
        {'category': 'status', 'content': 'Пристигнахме на място.'},
        {'category': 'status', 'content': 'Ситуацията е под контрол.'},
        {'category': 'status', 'content': 'Нуждаем се от подкрепление.'},
        {'category': 'status', 'content': 'Нуждаем се от вода.'},
        {'category': 'status', 'content': 'Има пострадали на място.'},
        {'category': 'status', 'content': 'Евакуацията приключи.'},
        {'category': 'request', 'content': 'Искам разрешение за използване на допълнителна техника.'},
        {'category': 'request', 'content': 'Моля за медицинска помощ на място.'},
        {'category': 'info', 'content': 'Вятърът се усили, посока североизток.'},
        {'category': 'info', 'content': 'Опасните вещества са идентифицирани.'},
    ]
    for td in templates_data:
        db.session.add(ChatTemplate(**td))

    db.session.commit()

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        seed_data()
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)
