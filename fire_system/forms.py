from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, FloatField, DateField, DateTimeField, PasswordField, BooleanField, IntegerField, FileField
from wtforms.validators import DataRequired, Email, Length, Optional, NumberRange
from flask_wtf.file import FileAllowed

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])

class EmployeeForm(FlaskForm):
    first_name = StringField('First Name', validators=[DataRequired(), Length(max=100)])
    last_name = StringField('Last Name', validators=[DataRequired(), Length(max=100)])
    rank_id = SelectField('Rank', coerce=int, validators=[Optional()])
    phone = StringField('Phone', validators=[Optional(), Length(max=20)])
    email = StringField('Email', validators=[Optional(), Email(), Length(max=120)])
    photo = FileField('Photo', validators=[FileAllowed(['jpg', 'jpeg', 'png', 'gif'], 'Images only!')])

class TeamForm(FlaskForm):
    name = StringField('Team Name', validators=[DataRequired(), Length(max=100)])
    shift = SelectField('Shift', choices=[('day', 'Day'), ('night', 'Night')], validators=[DataRequired()])
    leader_id = SelectField('Team Leader', coerce=int, validators=[Optional()])

class VehicleForm(FlaskForm):
    registration = StringField('Registration', validators=[DataRequired(), Length(max=20)])
    model = StringField('Model', validators=[DataRequired(), Length(max=100)])
    type = SelectField('Type', choices=[
        ('fire_engine', 'Fire Engine'),
        ('tanker', 'Tanker'),
        ('ladder', 'Ladder Truck'),
        ('rescue', 'Rescue Vehicle'),
        ('command', 'Command Vehicle'),
        ('other', 'Other')
    ], validators=[DataRequired()])
    gps_device_id = StringField('GPS Device ID', validators=[Optional(), Length(max=100)])

class IncidentForm(FlaskForm):
    incident_type = SelectField('Incident Type', choices=[
        ('fire', 'Fire'),
        ('car_accident', 'Car Accident'),
        ('flood', 'Flood'),
        ('earthquake', 'Earthquake'),
        ('chemical_spill', 'Chemical Spill'),
        ('gas_leak', 'Gas Leak'),
        ('forest_fire', 'Forest Fire'),
        ('rescue', 'Rescue'),
        ('explosion', 'Explosion'),
        ('other', 'Other')
    ], validators=[DataRequired()])
    priority = SelectField('Priority', choices=[('low', 'Low'), ('normal', 'Normal'), ('high', 'High'), ('critical', 'Critical')], default='normal')
    address = StringField('Address', validators=[DataRequired(), Length(max=255)])
    city = StringField('City', validators=[DataRequired(), Length(max=100)])
    latitude = FloatField('Latitude', validators=[Optional()])
    longitude = FloatField('Longitude', validators=[Optional()])
    description = TextAreaField('Description', validators=[Optional()])
    source = SelectField('Source', choices=[('112', '112'), ('direct', 'Direct Call'), ('other', 'Other')], default='112')
    team_id = SelectField('Assign Team', coerce=int, validators=[Optional()])

class AbsenceForm(FlaskForm):
    absence_type = SelectField('Type', choices=[
        ('vacation', 'Vacation'),
        ('sick', 'Sick Leave'),
        ('business_trip', 'Business Trip'),
        ('other', 'Other')
    ], validators=[DataRequired()])
    start_date = DateField('Start Date', validators=[DataRequired()])
    end_date = DateField('End Date', validators=[DataRequired()])
    reason = TextAreaField('Reason', validators=[Optional()])

class TaskForm(FlaskForm):
    title = StringField('Title', validators=[DataRequired(), Length(max=200)])
    description = TextAreaField('Description', validators=[Optional()])
    category = SelectField('Category', choices=[
        ('logistics', 'Logistics'),
        ('operational', 'Operational'),
        ('administrative', 'Administrative'),
        ('other', 'Other')
    ], default='operational')
    priority = SelectField('Priority', choices=[('low', 'Low'), ('normal', 'Normal'), ('high', 'High')], default='normal')
    employee_ids = StringField('Assign to (comma-separated IDs)')
    due_at = DateTimeField('Due Date/Time', format='%Y-%m-%dT%H:%M', validators=[Optional()])

class ResourceRequestForm(FlaskForm):
    resource_type = StringField('Resource Type', validators=[DataRequired(), Length(max=100)])
    quantity = StringField('Quantity', validators=[Optional(), Length(max=50)])
    description = TextAreaField('Description', validators=[Optional()])

class ChatMessageForm(FlaskForm):
    content = TextAreaField('Message', validators=[Optional()])
    image = FileField('Image', validators=[FileAllowed(['jpg', 'jpeg', 'png', 'gif'], 'Images only!')])

class MapMarkerForm(FlaskForm):
    marker_type = SelectField('Marker Type', choices=[
        ('fire_front', 'Fire Front'),
        ('wind_direction', 'Wind Direction'),
        ('water_source', 'Water Source'),
        ('danger_zone', 'Danger Zone'),
        ('command_post', 'Command Post'),
        ('evacuation_point', 'Evacuation Point'),
        ('other', 'Other')
    ], validators=[DataRequired()])
    label = StringField('Label', validators=[Optional(), Length(max=200)])
    latitude = FloatField('Latitude', validators=[DataRequired()])
    longitude = FloatField('Longitude', validators=[DataRequired()])
