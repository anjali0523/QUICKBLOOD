import os
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['SECRET_KEY'] = 'quickblood-secret-key-2026-hyper-vibrant'
db_path = os.path.join(app.root_path, 'quickblood.db')
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ---------------------------------------------------------------------------
# Database Models (SQL)
# ---------------------------------------------------------------------------

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='Donor') # 'Donor', 'Receiver', 'Both'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    donor_profile = db.relationship('DonorProfile', backref='user', uselist=False, cascade="all, delete-orphan")
    requests = db.relationship('BloodRequest', backref='requester', lazy=True, foreign_keys='BloodRequest.user_id')
    assigned_donations = db.relationship('BloodRequest', backref='assigned_donor', lazy=True, foreign_keys='BloodRequest.donor_id')
    donation_history = db.relationship('DonationRecord', backref='donor', lazy=True, foreign_keys='DonationRecord.donor_id', order_by='DonationRecord.donation_date.desc()')

class DonorProfile(db.Model):
    __tablename__ = 'donor_profiles'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    blood_group = db.Column(db.String(5), nullable=False) # A+, A-, B+, B-, AB+, AB-, O+, O-
    city = db.Column(db.String(100), nullable=False)
    state = db.Column(db.String(100), nullable=True, default='')
    is_available = db.Column(db.Boolean, default=True, nullable=False)
    last_donated = db.Column(db.String(20), nullable=True, default='Never')
    units_donated = db.Column(db.Integer, default=1)
    notes = db.Column(db.String(250), nullable=True, default='Healthy donor ready to save lives.')
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @property
    def eligibility(self):
        """Calculates eligibility and days remaining in standard 56-day cooling window."""
        if not self.last_donated or str(self.last_donated).strip().lower() in ['never', 'none', '']:
            return {
                'is_eligible': True,
                'days_since': None,
                'days_remaining': 0,
                'status_label': 'Eligible to Donate',
                'badge_class': 'status-available',
                'message': 'No recent donation on record. Ready to donate anytime.'
            }
        try:
            date_part = str(self.last_donated).strip()[:10]
            last_date = datetime.strptime(date_part, '%Y-%m-%d').date()
            today = datetime.utcnow().date()
            days_since = (today - last_date).days
            if days_since < 0:
                days_since = 0
            COOLING_DAYS = 56
            if days_since >= COOLING_DAYS:
                return {
                    'is_eligible': True,
                    'days_since': days_since,
                    'days_remaining': 0,
                    'status_label': 'Eligible to Donate',
                    'badge_class': 'status-available',
                    'message': f'56-day rest cycle completed ({days_since} days since last donation).'
                }
            else:
                remaining = COOLING_DAYS - days_since
                return {
                    'is_eligible': False,
                    'days_since': days_since,
                    'days_remaining': remaining,
                    'status_label': f'Cooling Period ({remaining}d left)',
                    'badge_class': 'status-cooling',
                    'message': f'Donated {days_since} day(s) ago. Standard recovery recommended for {remaining} more day(s).'
                }
        except Exception:
            return {
                'is_eligible': True,
                'days_since': None,
                'days_remaining': 0,
                'status_label': 'Eligible to Donate',
                'badge_class': 'status-available',
                'message': 'Ready to donate.'
            }

class BloodRequest(db.Model):
    __tablename__ = 'blood_requests'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False) # Requester
    donor_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True) # Assigned Donor
    patient_name = db.Column(db.String(100), nullable=False)
    blood_group = db.Column(db.String(5), nullable=False)
    hospital_name = db.Column(db.String(150), nullable=False)
    city = db.Column(db.String(100), nullable=False)
    units_needed = db.Column(db.Integer, default=1)
    urgency = db.Column(db.String(20), default='Normal') # 'Normal', 'Urgent', 'Critical Emergency'
    contact_phone = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(30), default='Pending') # 'Pending', 'Accepted', 'Donation in Progress', 'Fulfilled', 'Cancelled', 'Rejected'
    donor_completed = db.Column(db.Boolean, default=False)
    donor_completed_at = db.Column(db.DateTime, nullable=True)
    accepted_at = db.Column(db.DateTime, nullable=True)
    fulfilled_at = db.Column(db.DateTime, nullable=True)
    cancelled_at = db.Column(db.DateTime, nullable=True)
    rejection_reason = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    donation_records = db.relationship('DonationRecord', backref='blood_request', lazy=True)

    @property
    def status_badge_class(self):
        mapping = {
            'Pending': 'status-pending',
            'Accepted': 'status-accepted',
            'Donation in Progress': 'status-in-progress',
            'Fulfilled': 'status-fulfilled',
            'Cancelled': 'status-cancelled',
            'Rejected': 'status-rejected'
        }
        return mapping.get(self.status, 'status-pending')

    @property
    def status_icon(self):
        mapping = {
            'Pending': 'fa-hourglass-start',
            'Accepted': 'fa-handshake',
            'Donation in Progress': 'fa-syringe',
            'Fulfilled': 'fa-circle-check',
            'Cancelled': 'fa-ban',
            'Rejected': 'fa-circle-xmark'
        }
        return mapping.get(self.status, 'fa-info-circle')

    @property
    def progress_step(self):
        if self.status == 'Pending':
            return 1
        elif self.status == 'Accepted':
            return 2
        elif self.status == 'Donation in Progress':
            return 3
        elif self.status == 'Fulfilled':
            return 4
        return 0

class DonationRecord(db.Model):
    __tablename__ = 'donation_records'
    id = db.Column(db.Integer, primary_key=True)
    donor_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    request_id = db.Column(db.Integer, db.ForeignKey('blood_requests.id'), nullable=True)
    patient_name = db.Column(db.String(100), nullable=False)
    blood_group = db.Column(db.String(5), nullable=False)
    hospital_name = db.Column(db.String(150), nullable=False)
    city = db.Column(db.String(100), nullable=False)
    units = db.Column(db.Integer, default=1)
    donation_date = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(40), default='Completed') # 'Completed', 'Fulfilled & Received'
    notes = db.Column(db.String(255), nullable=True)

# ---------------------------------------------------------------------------
# Seed & Migration Helpers
# ---------------------------------------------------------------------------

def init_and_migrate_db():
    db.create_all()
    import sqlite3
    db_file = os.path.join(app.root_path, 'quickblood.db')
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(blood_requests)")
    cols = [r[1] for r in cursor.fetchall()]
    needed_columns = [
        ('donor_id', 'INTEGER'),
        ('accepted_at', 'DATETIME'),
        ('donor_completed', 'BOOLEAN DEFAULT 0'),
        ('donor_completed_at', 'DATETIME'),
        ('fulfilled_at', 'DATETIME'),
        ('cancelled_at', 'DATETIME'),
        ('rejection_reason', 'VARCHAR(255)')
    ]
    for col_name, col_def in needed_columns:
        if col_name not in cols:
            cursor.execute(f"ALTER TABLE blood_requests ADD COLUMN {col_name} {col_def}")
    conn.commit()
    conn.close()

    # Seed past donation history for donors if empty
    if DonationRecord.query.count() == 0:
        donors_with_donations = DonorProfile.query.filter(DonorProfile.units_donated > 0).all()
        for dp in donors_with_donations:
            if dp.last_donated and dp.last_donated != 'Never':
                try:
                    d_date = datetime.strptime(dp.last_donated[:10], '%Y-%m-%d')
                except Exception:
                    d_date = datetime.utcnow() - timedelta(days=60)
                rec = DonationRecord(
                    donor_id=dp.user_id,
                    patient_name=f"Community Patient ({dp.blood_group})",
                    blood_group=dp.blood_group,
                    hospital_name=f"Regional Blood Bank, {dp.city}",
                    city=dp.city,
                    units=dp.units_donated,
                    donation_date=d_date,
                    status='Fulfilled & Received',
                    notes='Voluntary blood drive donation verified by health authorities.'
                )
                db.session.add(rec)
        db.session.commit()

def seed_database():
    # If Nashik donor data already exists, no need to re-seed
    nashik_donor = DonorProfile.query.filter(DonorProfile.city.ilike('%Nashik%')).first()
    if nashik_donor:
        return

    # Clear old non-Nashik demo data if completely absent
    db.session.query(DonationRecord).delete()
    db.session.query(BloodRequest).delete()
    db.session.query(DonorProfile).delete()
    db.session.query(User).delete()
    db.session.commit()

    demo_users_data = [
        {"name": "Rajesh Patil", "email": "rajesh.patil@example.com", "phone": "+91 98220 12345", "role": "Donor", "bg": "O-", "city": "Nashik", "avail": True, "units": 5, "last": "2026-07-15", "notes": "Universal donor O- on College Road, Nashik. Active volunteer."},
        {"name": "Aarti Kulkarni", "email": "aarti.k@example.com", "phone": "+91 98221 23456", "role": "Donor", "bg": "A+", "city": "Nashik", "avail": True, "units": 3, "last": "2026-06-10", "notes": "Regular donor near Panchavati, Nashik."},
        {"name": "Sachin Deshmukh", "email": "sachin.d@example.com", "phone": "+91 98222 34567", "role": "Donor", "bg": "B+", "city": "Nashik", "avail": True, "units": 8, "last": "2026-08-01", "notes": "Whole blood & plasma donor near Nashik Road Station."},
        {"name": "Pooja Jadhav", "email": "pooja.j@example.com", "phone": "+91 98223 45678", "role": "Donor", "bg": "AB+", "city": "Nashik", "avail": True, "units": 2, "last": "2026-05-20", "notes": "Universal recipient & plasma donor in CIDCO Nashik."},
        {"name": "Ganesh Shinde", "email": "ganesh.s@example.com", "phone": "+91 98224 56789", "role": "Donor", "bg": "O+", "city": "Nashik", "avail": True, "units": 6, "last": "2026-08-12", "notes": "Ready to donate anytime near Indira Nagar, Nashik."},
        {"name": "Vikram Chaudhari", "email": "vikram.c@example.com", "phone": "+91 98225 67890", "role": "Donor", "bg": "A-", "city": "Nashik", "avail": True, "units": 4, "last": "2026-07-22", "notes": "Available near Satpur MIDC, Nashik."},
        {"name": "Snehal Pawar", "email": "snehal.p@example.com", "phone": "+91 98226 78901", "role": "Donor", "bg": "B-", "city": "Nashik", "avail": True, "units": 3, "last": "2026-08-18", "notes": "Rare B- blood group donor on Gangapur Road, Nashik."},
        {"name": "Amit Joshi", "email": "amit.j@example.com", "phone": "+91 98227 89012", "role": "Donor", "bg": "AB-", "city": "Pune", "avail": False, "units": 1, "last": "2026-09-01", "notes": "Available near Pune-Nashik highway corridor."},
        {"name": "Rohan More", "email": "rohan.m@example.com", "phone": "+91 98228 90123", "role": "Donor", "bg": "O-", "city": "Chhatrapati Sambhajinagar", "avail": True, "units": 4, "last": "2026-06-25", "notes": "Universal donor O- near Nashik region."},
        {"name": "Neha Marathe", "email": "neha.m@example.com", "phone": "+91 98229 01234", "role": "Both", "bg": "A+", "city": "Nashik", "avail": True, "units": 3, "last": "2026-07-04", "notes": "Donor & requester near Mahatma Nagar, Nashik."}
    ]

    for u_info in demo_users_data:
        user = User(
            name=u_info['name'],
            email=u_info['email'],
            password_hash=generate_password_hash('password123'),
            phone=u_info['phone'],
            role=u_info['role']
        )
        db.session.add(user)
        db.session.commit()

        donor = DonorProfile(
            user_id=user.id,
            blood_group=u_info['bg'],
            city=u_info['city'],
            is_available=u_info['avail'],
            last_donated=u_info['last'],
            units_donated=u_info['units'],
            notes=u_info['notes']
        )
        db.session.add(donor)

    # Seed emergency blood requests
    req1 = BloodRequest(
        user_id=1,
        patient_name="Suresh Gawande",
        blood_group="O-",
        hospital_name="Sahyadri Super Speciality Hospital, Mumbai Naka",
        city="Nashik",
        units_needed=2,
        urgency="Critical Emergency",
        contact_phone="+91 98220 12345",
        status="Pending"
    )
    req2 = BloodRequest(
        user_id=3,
        patient_name="Sunita Bhusari",
        blood_group="B+",
        hospital_name="Wockhardt Hospital, Wani House",
        city="Nashik",
        units_needed=3,
        urgency="Urgent",
        contact_phone="+91 98222 34567",
        status="Pending"
    )
    req3 = BloodRequest(
        user_id=7,
        patient_name="Mahesh Sanap",
        blood_group="B-",
        hospital_name="HCG Manavata Cancer Centre",
        city="Nashik",
        units_needed=1,
        urgency="Critical Emergency",
        contact_phone="+91 98226 78901",
        status="Pending"
    )
    db.session.add_all([req1, req2, req3])
    db.session.commit()
    print("QUICKBLOOD database initialized with Nashik records!")

# ---------------------------------------------------------------------------
# Helper Context Processors
# ---------------------------------------------------------------------------

@app.context_processor
def inject_current_user():
    user = None
    if 'user_id' in session:
        user = User.query.get(session['user_id'])
    return dict(current_user=user)

# ---------------------------------------------------------------------------
# Routes & Controllers
# ---------------------------------------------------------------------------

@app.route('/')
def index():
    total_donors = DonorProfile.query.count()
    available_donors = DonorProfile.query.filter_by(is_available=True).count()
    active_requests = BloodRequest.query.filter(BloodRequest.status.in_(['Pending', 'Accepted', 'Donation in Progress'])).count()
    
    critical_requests = BloodRequest.query.filter(
        BloodRequest.status.in_(['Pending', 'Accepted'])
    ).order_by(BloodRequest.created_at.desc()).limit(3).all()
    
    cities = [c[0] for c in db.session.query(DonorProfile.city).distinct().order_by(DonorProfile.city).all()]

    return render_template(
        'index.html',
        total_donors=total_donors,
        available_donors=available_donors,
        active_requests=active_requests,
        critical_requests=critical_requests,
        cities=cities
    )

@app.route('/donors')
def donors():
    bg_filter = request.args.get('blood_group', '').strip()
    city_filter = request.args.get('city', '').strip()
    avail_filter = request.args.get('available_only', '1')

    query = db.session.query(DonorProfile, User).join(User, DonorProfile.user_id == User.id)

    if bg_filter:
        query = query.filter(DonorProfile.blood_group == bg_filter)
    if city_filter:
        query = query.filter(DonorProfile.city.ilike(f"%{city_filter}%"))
    if avail_filter == '1':
        query = query.filter(DonorProfile.is_available == True)

    donors_list = query.order_by(DonorProfile.is_available.desc(), User.name.asc()).all()
    cities = [c[0] for c in db.session.query(DonorProfile.city).distinct().order_by(DonorProfile.city).all()]

    return render_template(
        'donors.html',
        donors=donors_list,
        selected_bg=bg_filter,
        selected_city=city_filter,
        available_only=avail_filter,
        cities=cities
    )

@app.route('/api/donors')
def api_donors():
    bg_filter = request.args.get('blood_group', '').strip()
    city_filter = request.args.get('city', '').strip()
    avail_filter = request.args.get('available_only', '1')

    query = db.session.query(DonorProfile, User).join(User, DonorProfile.user_id == User.id)

    if bg_filter:
        query = query.filter(DonorProfile.blood_group == bg_filter)
    if city_filter:
        query = query.filter(DonorProfile.city.ilike(f"%{city_filter}%"))
    if avail_filter == '1':
        query = query.filter(DonorProfile.is_available == True)

    donors_list = query.order_by(DonorProfile.is_available.desc()).all()

    result = []
    for d, u in donors_list:
        result.append({
            'id': d.id,
            'name': u.name,
            'email': u.email,
            'phone': u.phone,
            'blood_group': d.blood_group,
            'city': d.city,
            'is_available': d.is_available,
            'status_text': 'Available' if d.is_available else 'Unavailable',
            'last_donated': d.last_donated or 'Never',
            'units_donated': d.units_donated,
            'notes': d.notes
        })
    return jsonify({'success': True, 'count': len(result), 'donors': result})

@app.route('/requests')
def requests_feed():
    status_filter = request.args.get('status', 'Pending').strip()
    bg_filter = request.args.get('blood_group', '').strip()
    city_filter = request.args.get('city', '').strip()

    query = BloodRequest.query
    if status_filter and status_filter.lower() != 'all':
        if status_filter == 'Active':
            query = query.filter(BloodRequest.status.in_(['Pending', 'Accepted', 'Donation in Progress']))
        else:
            query = query.filter_by(status=status_filter)
    
    if bg_filter:
        query = query.filter_by(blood_group=bg_filter)
    if city_filter:
        query = query.filter(BloodRequest.city.ilike(f"%{city_filter}%"))

    requests_list = query.order_by(BloodRequest.created_at.desc()).all()
    cities = [c[0] for c in db.session.query(BloodRequest.city).distinct().order_by(BloodRequest.city).all()]

    return render_template(
        'requests.html',
        requests_list=requests_list,
        selected_status=status_filter,
        selected_bg=bg_filter,
        selected_city=city_filter,
        cities=cities
    )

@app.route('/requests/new', methods=['POST'])
def new_request():
    if 'user_id' not in session:
        flash('Please login to post a blood request.', 'warning')
        return redirect(url_for('login'))

    patient_name = request.form.get('patient_name', '').strip()
    blood_group = request.form.get('blood_group', '').strip()
    hospital_name = request.form.get('hospital_name', '').strip()
    city = request.form.get('city', '').strip()
    units_needed = int(request.form.get('units_needed', 1))
    urgency = request.form.get('urgency', 'Urgent')
    contact_phone = request.form.get('contact_phone', '').strip()

    if not all([patient_name, blood_group, hospital_name, city, contact_phone]):
        flash('Please fill in all required fields.', 'danger')
        return redirect(url_for('requests_feed'))

    req_obj = BloodRequest(
        user_id=session['user_id'],
        patient_name=patient_name,
        blood_group=blood_group,
        hospital_name=hospital_name,
        city=city,
        units_needed=units_needed,
        urgency=urgency,
        contact_phone=contact_phone,
        status='Pending'
    )
    db.session.add(req_obj)
    db.session.commit()

    flash(f'Emergency Blood Request posted for {patient_name} ({blood_group}) in {city}!', 'success')
    return redirect(url_for('dashboard'))

# ---------------------------------------------------------------------------
# Request Lifecycle Actions (Accept, In Progress, Completed, Received, Cancel)
# ---------------------------------------------------------------------------

@app.route('/requests/<int:req_id>/accept', methods=['POST'])
def accept_request(req_id):
    if 'user_id' not in session:
        flash('Please login to volunteer for this request.', 'warning')
        return redirect(url_for('login'))

    user = User.query.get_or_404(session['user_id'])
    if not user.donor_profile and user.role not in ['Donor', 'Both']:
        flash('You must have a donor profile to accept blood requests.', 'danger')
        return redirect(url_for('requests_feed'))

    req_obj = BloodRequest.query.get_or_404(req_id)

    # Prevent accepting own request
    if req_obj.user_id == user.id:
        flash('You cannot accept your own blood request.', 'warning')
        return redirect(url_for('requests_feed'))

    # Check status
    if req_obj.status != 'Pending':
        flash(f'This request is currently in "{req_obj.status}" status and cannot be accepted.', 'warning')
        return redirect(url_for('requests_feed'))

    req_obj.status = 'Accepted'
    req_obj.donor_id = user.id
    req_obj.accepted_at = datetime.utcnow()
    db.session.commit()

    flash(f'Thank you! You have accepted the request for {req_obj.patient_name} ({req_obj.blood_group}) at {req_obj.hospital_name}.', 'success')
    return redirect(url_for('dashboard'))

@app.route('/requests/<int:req_id>/start-progress', methods=['POST'])
def start_donation_progress(req_id):
    if 'user_id' not in session:
        flash('Please login.', 'warning')
        return redirect(url_for('login'))

    req_obj = BloodRequest.query.get_or_404(req_id)
    if req_obj.donor_id != session['user_id'] and req_obj.user_id != session['user_id']:
        flash('Unauthorized action.', 'danger')
        return redirect(url_for('dashboard'))

    if req_obj.status == 'Accepted':
        req_obj.status = 'Donation in Progress'
        db.session.commit()
        flash('Donation marked as in progress. Proceed with donation at the hospital.', 'info')
    else:
        flash(f'Cannot change status from {req_obj.status} to Donation in Progress.', 'warning')

    return redirect(url_for('dashboard'))

@app.route('/requests/<int:req_id>/mark-completed', methods=['POST'])
def mark_donation_completed(req_id):
    if 'user_id' not in session:
        if request.is_json:
            return jsonify({'success': False, 'message': 'Unauthorized'}), 401
        flash('Please login to complete donation.', 'warning')
        return redirect(url_for('login'))

    req_obj = BloodRequest.query.get_or_404(req_id)
    user = User.query.get(session['user_id'])

    # Validation: Only assigned donor can mark donation completed
    if req_obj.donor_id != user.id:
        if request.is_json:
            return jsonify({'success': False, 'message': 'Only the assigned donor can mark this donation completed.'}), 403
        flash('Only the assigned donor can mark this donation as completed.', 'danger')
        return redirect(url_for('dashboard'))

    # Validation: Valid states
    if req_obj.status not in ['Accepted', 'Donation in Progress']:
        msg = f'Cannot complete donation for a request with status "{req_obj.status}".'
        if request.is_json:
            return jsonify({'success': False, 'message': msg}), 400
        flash(msg, 'warning')
        return redirect(url_for('dashboard'))

    # Prevent duplicate action
    if req_obj.donor_completed:
        msg = 'This donation has already been marked as completed by you. Awaiting recipient confirmation.'
        if request.is_json:
            return jsonify({'success': False, 'message': msg}), 400
        flash(msg, 'info')
        return redirect(url_for('dashboard'))

    today_str = datetime.utcnow().strftime('%Y-%m-%d')

    # 1. Update Request
    req_obj.status = 'Donation in Progress'
    req_obj.donor_completed = True
    req_obj.donor_completed_at = datetime.utcnow()

    # 2. Update Donor availability and stats
    if user.donor_profile:
        user.donor_profile.is_available = False
        user.donor_profile.last_donated = today_str
        user.donor_profile.units_donated = (user.donor_profile.units_donated or 0) + (req_obj.units_needed or 1)

    # 3. Add to Donation History Records
    donation_record = DonationRecord(
        donor_id=user.id,
        request_id=req_obj.id,
        patient_name=req_obj.patient_name,
        blood_group=req_obj.blood_group,
        hospital_name=req_obj.hospital_name,
        city=req_obj.city,
        units=req_obj.units_needed or 1,
        donation_date=datetime.utcnow(),
        status='Completed (Awaiting Recipient Confirmation)',
        notes=f'Blood donation completed for patient {req_obj.patient_name} at {req_obj.hospital_name}.'
    )
    db.session.add(donation_record)
    db.session.commit()

    success_msg = f'Donation completed! You have been automatically marked Unavailable, and your donation history has been updated. Thank you for saving a life!'
    
    if request.is_json:
        return jsonify({
            'success': True,
            'message': success_msg,
            'request_status': req_obj.status,
            'donor_available': False,
            'last_donated': today_str
        })

    flash(success_msg, 'success')
    return redirect(url_for('dashboard'))

@app.route('/requests/<int:req_id>/confirm-received', methods=['POST'])
@app.route('/requests/<int:req_id>/fulfill', methods=['POST'])
def fulfill_request(req_id):
    if 'user_id' not in session:
        if request.is_json:
            return jsonify({'success': False, 'message': 'Unauthorized'}), 401
        flash('Unauthorized action. Please login.', 'danger')
        return redirect(url_for('login'))

    req_obj = BloodRequest.query.get_or_404(req_id)
    
    # Validation: Only the creator (recipient) can confirm blood received
    if req_obj.user_id != session['user_id']:
        if request.is_json:
            return jsonify({'success': False, 'message': 'Only the requester can confirm blood received.'}), 403
        flash('Only the creator of this request can confirm blood received.', 'danger')
        return redirect(url_for('dashboard'))

    # Prevent duplicate action
    if req_obj.status == 'Fulfilled':
        msg = 'This blood request is already marked as Fulfilled.'
        if request.is_json:
            return jsonify({'success': False, 'message': msg}), 400
        flash(msg, 'info')
        return redirect(url_for('dashboard'))

    if req_obj.status in ['Cancelled', 'Rejected']:
        msg = f'Cannot fulfill a {req_obj.status} request.'
        if request.is_json:
            return jsonify({'success': False, 'message': msg}), 400
        flash(msg, 'danger')
        return redirect(url_for('dashboard'))

    # Update status to Fulfilled
    req_obj.status = 'Fulfilled'
    req_obj.fulfilled_at = datetime.utcnow()

    # Update associated donation history status
    existing_record = DonationRecord.query.filter_by(request_id=req_obj.id).first()
    if existing_record:
        existing_record.status = 'Fulfilled & Received'
    elif req_obj.donor_id:
        # If recipient confirmed directly, record donation history for the assigned donor
        donor_user = User.query.get(req_obj.donor_id)
        if donor_user:
            if donor_user.donor_profile:
                donor_user.donor_profile.is_available = False
                donor_user.donor_profile.last_donated = datetime.utcnow().strftime('%Y-%m-%d')
                donor_user.donor_profile.units_donated = (donor_user.donor_profile.units_donated or 0) + (req_obj.units_needed or 1)
            
            new_rec = DonationRecord(
                donor_id=donor_user.id,
                request_id=req_obj.id,
                patient_name=req_obj.patient_name,
                blood_group=req_obj.blood_group,
                hospital_name=req_obj.hospital_name,
                city=req_obj.city,
                units=req_obj.units_needed or 1,
                donation_date=datetime.utcnow(),
                status='Fulfilled & Received',
                notes=f'Blood received and confirmed by requester for patient {req_obj.patient_name}.'
            )
            db.session.add(new_rec)

    db.session.commit()

    success_msg = f'Blood received successfully! Request for {req_obj.patient_name} is now Fulfilled.'
    if request.is_json:
        return jsonify({
            'success': True,
            'message': success_msg,
            'status': 'Fulfilled'
        })

    flash(success_msg, 'success')
    return redirect(url_for('dashboard'))

@app.route('/requests/<int:req_id>/cancel', methods=['POST'])
def cancel_request(req_id):
    if 'user_id' not in session:
        flash('Unauthorized action.', 'danger')
        return redirect(url_for('login'))

    req_obj = BloodRequest.query.get_or_404(req_id)
    if req_obj.user_id != session['user_id']:
        flash('Only the creator of this request can cancel it.', 'danger')
        return redirect(url_for('dashboard'))

    if req_obj.status == 'Fulfilled':
        flash('Fulfilled requests cannot be cancelled.', 'warning')
        return redirect(url_for('dashboard'))

    req_obj.status = 'Cancelled'
    req_obj.cancelled_at = datetime.utcnow()
    db.session.commit()

    flash(f'Request for {req_obj.patient_name} has been cancelled.', 'info')
    return redirect(url_for('dashboard'))

@app.route('/requests/<int:req_id>/reject', methods=['POST'])
def reject_request(req_id):
    if 'user_id' not in session:
        flash('Unauthorized action.', 'danger')
        return redirect(url_for('login'))

    req_obj = BloodRequest.query.get_or_404(req_id)
    if req_obj.user_id != session['user_id'] and req_obj.donor_id != session['user_id']:
        flash('Unauthorized action.', 'danger')
        return redirect(url_for('dashboard'))

    reason = request.form.get('reason', 'Donor or requester unable to proceed').strip()
    action_type = request.form.get('action_type', 'reject_request')

    if action_type == 'unassign':
        # Unassign donor so request returns to Pending for others
        req_obj.donor_id = None
        req_obj.status = 'Pending'
        req_obj.donor_completed = False
        flash('Donor assignment removed. Request is now Pending for other donors.', 'info')
    else:
        req_obj.status = 'Rejected'
        req_obj.rejection_reason = reason
        flash(f'Request status marked as Rejected: {reason}', 'warning')

    db.session.commit()
    return redirect(url_for('dashboard'))

@app.route('/requests/<int:req_id>/reopen', methods=['POST'])
def reopen_request(req_id):
    if 'user_id' not in session:
        flash('Unauthorized action.', 'danger')
        return redirect(url_for('login'))

    req_obj = BloodRequest.query.get_or_404(req_id)
    if req_obj.user_id != session['user_id']:
        flash('Only the creator can reopen this request.', 'danger')
        return redirect(url_for('dashboard'))

    req_obj.status = 'Pending'
    req_obj.donor_id = None
    req_obj.donor_completed = False
    req_obj.cancelled_at = None
    req_obj.rejection_reason = None
    db.session.commit()

    flash(f'Request for {req_obj.patient_name} reopened as Pending.', 'success')
    return redirect(url_for('dashboard'))

# ---------------------------------------------------------------------------
# Donor Availability & Profile Controls
# ---------------------------------------------------------------------------

@app.route('/api/toggle-availability', methods=['POST', 'GET'])
def toggle_availability():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    user = User.query.get(session['user_id'])
    if not user or not user.donor_profile:
        return jsonify({'success': False, 'message': 'Donor profile not found'}), 404

    donor = user.donor_profile
    
    # Check if target state was explicitly specified
    target_state = None
    if request.is_json and 'is_available' in request.json:
        target_state = bool(request.json['is_available'])
    elif 'is_available' in request.form:
        target_state = request.form.get('is_available') in ['1', 'true', 'True']
    
    if target_state is not None:
        donor.is_available = target_state
    else:
        donor.is_available = not donor.is_available
        
    db.session.commit()

    status_str = 'Available' if donor.is_available else 'Unavailable'
    return jsonify({
        'success': True,
        'is_available': donor.is_available,
        'status_text': status_str,
        'badge_class': 'status-available' if donor.is_available else 'status-unavailable',
        'message': f'Donation status successfully updated to {status_str}.'
    })

@app.route('/dashboard/toggle-availability', methods=['POST'])
def dashboard_toggle_availability():
    if 'user_id' not in session:
        flash('Please login.', 'warning')
        return redirect(url_for('login'))

    user = User.query.get(session['user_id'])
    if not user or not user.donor_profile:
        flash('Donor profile not found.', 'danger')
        return redirect(url_for('dashboard'))

    target_status = request.form.get('target_status')
    if target_status == 'Available':
        user.donor_profile.is_available = True
    elif target_status == 'Unavailable':
        user.donor_profile.is_available = False
    else:
        user.donor_profile.is_available = not user.donor_profile.is_available

    db.session.commit()
    new_status = 'Available' if user.donor_profile.is_available else 'Unavailable'
    flash(f'Your donation status is now {new_status}.', 'success')
    return redirect(url_for('dashboard'))

@app.route('/dashboard/update-profile', methods=['POST'])
def update_profile():
    if 'user_id' not in session:
        flash('Unauthorized.', 'danger')
        return redirect(url_for('login'))

    user = User.query.get(session['user_id'])
    user.phone = request.form.get('phone', user.phone).strip()

    if user.donor_profile:
        user.donor_profile.blood_group = request.form.get('blood_group', user.donor_profile.blood_group)
        user.donor_profile.city = request.form.get('city', user.donor_profile.city).strip()
        last_d = request.form.get('last_donated', '').strip()
        if last_d:
            user.donor_profile.last_donated = last_d
        user.donor_profile.notes = request.form.get('notes', user.donor_profile.notes).strip()

    db.session.commit()
    flash('Profile updated successfully!', 'success')
    return redirect(url_for('dashboard'))

# ---------------------------------------------------------------------------
# Authentication Routes
# ---------------------------------------------------------------------------

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').lower().strip()
        password = request.form.get('password', '')
        phone = request.form.get('phone', '').strip()
        role = request.form.get('role', 'Donor')
        blood_group = request.form.get('blood_group', '').strip()
        city = request.form.get('city', '').strip()
        notes = request.form.get('notes', '').strip()

        if User.query.filter_by(email=email).first():
            flash('Email is already registered. Please login instead.', 'danger')
            return redirect(url_for('register'))

        new_user = User(
            name=name,
            email=email,
            password_hash=generate_password_hash(password),
            phone=phone,
            role=role
        )
        db.session.add(new_user)
        db.session.commit()

        if role in ['Donor', 'Both'] and blood_group and city:
            donor_profile = DonorProfile(
                user_id=new_user.id,
                blood_group=blood_group,
                city=city,
                is_available=True,
                notes=notes or 'Registered donor ready to help.'
            )
            db.session.add(donor_profile)
            db.session.commit()

        session['user_id'] = new_user.id
        session['user_name'] = new_user.name
        session['user_role'] = new_user.role

        flash(f'Welcome to QUICKBLOOD, {name}! Account created successfully.', 'success')
        return redirect(url_for('dashboard'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').lower().strip()
        password = request.form.get('password', '')

        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password_hash, password):
            session['user_id'] = user.id
            session['user_name'] = user.name
            session['user_role'] = user.role
            flash(f'Welcome back, {user.name}!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid email address or password.', 'danger')

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully.', 'info')
    return redirect(url_for('index'))

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        flash('Please login to access your dashboard.', 'warning')
        return redirect(url_for('login'))

    user = User.query.get_or_404(session['user_id'])
    donor = user.donor_profile

    # Recipient requests
    all_user_requests = BloodRequest.query.filter_by(user_id=user.id).order_by(BloodRequest.created_at.desc()).all()
    active_requests = [r for r in all_user_requests if r.status in ['Pending', 'Accepted', 'Donation in Progress']]
    completed_requests = [r for r in all_user_requests if r.status in ['Fulfilled', 'Cancelled', 'Rejected']]

    # Donor accepted donations
    all_assigned = BloodRequest.query.filter_by(donor_id=user.id).order_by(BloodRequest.created_at.desc()).all()
    active_assigned = [r for r in all_assigned if r.status in ['Accepted', 'Donation in Progress']]
    past_assigned = [r for r in all_assigned if r.status in ['Fulfilled', 'Cancelled', 'Rejected']]

    # Donation history records
    donation_history = DonationRecord.query.filter_by(donor_id=user.id).order_by(DonationRecord.donation_date.desc()).all()

    today_str = datetime.utcnow().strftime('%Y-%m-%d')

    return render_template(
        'dashboard.html',
        user=user,
        donor=donor,
        requests=all_user_requests,
        active_requests=active_requests,
        completed_requests=completed_requests,
        active_assigned=active_assigned,
        past_assigned=past_assigned,
        donation_history=donation_history,
        today_str=today_str
    )

# ---------------------------------------------------------------------------
# Application Initialization
# ---------------------------------------------------------------------------

with app.app_context():
    init_and_migrate_db()
    seed_database()

if __name__ == '__main__':
    app.run(debug=True, port=5000)
