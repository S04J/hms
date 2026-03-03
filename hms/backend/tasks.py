from celery import Celery
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import csv
import io
import json
import requests
from datetime import datetime, date, timedelta


def make_celery(app):
    celery = Celery(
        app.import_name,
        backend=app.config.get('CELERY_RESULT_BACKEND', 'redis://localhost:6379/1'),
        broker=app.config.get('CELERY_BROKER_URL', 'redis://localhost:6379/1')
    )
    celery.conf.update(app.config)

    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    celery.Task = ContextTask
    return celery


def send_email(to_email, subject, body_html, config):
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = config.get('MAIL_DEFAULT_SENDER', 'hms@hospital.com')
        msg['To'] = to_email
        part = MIMEText(body_html, 'html')
        msg.attach(part)

        with smtplib.SMTP(config.get('MAIL_SERVER', 'smtp.gmail.com'), 587) as server:
            server.starttls()
            server.login(config.get('MAIL_USERNAME'), config.get('MAIL_PASSWORD'))
            server.sendmail(msg['From'], to_email, msg.as_string())
        return True
    except Exception as e:
        print(f"Email send error: {e}")
        return False


def send_gchat_notification(webhook_url, message):
    try:
        payload = {"text": message}
        resp = requests.post(webhook_url, json=payload, timeout=5)
        return resp.status_code == 200
    except Exception as e:
        print(f"GChat notification error: {e}")
        return False


def register_tasks(celery, app):

    @celery.task(name='tasks.send_daily_reminders')
    def send_daily_reminders():
        from backend.models import Appointment, Patient, User
        today = date.today()
        appointments = Appointment.query.filter_by(date=today, status='Booked').all()
        
        for apt in appointments:
            patient = apt.patient
            if patient and patient.user:
                message = (
                    f"Hospital Reminder: Dear {patient.full_name}, "
                    f"you have an appointment with Dr. {apt.doctor.full_name} "
                    f"today ({today.strftime('%d %b %Y')}) during the {apt.time_slot} slot. "
                    f"Please visit on time."
                )
                # Send via GChat if webhook configured
                webhook = app.config.get('GCHAT_WEBHOOK_URL')
                if webhook:
                    send_gchat_notification(webhook, message)
                
                # Send email
                html = f"""
                <html><body>
                <h2>Hospital Appointment Reminder</h2>
                <p>Dear {patient.full_name},</p>
                <p>This is a reminder that you have an appointment scheduled for today.</p>
                <ul>
                    <li><strong>Doctor:</strong> {apt.doctor.full_name}</li>
                    <li><strong>Department:</strong> {apt.doctor.department.name if apt.doctor.department else 'N/A'}</li>
                    <li><strong>Date:</strong> {today.strftime('%d %B %Y')}</li>
                    <li><strong>Slot:</strong> {apt.time_slot}</li>
                </ul>
                <p>Please be on time. Thank you!</p>
                </body></html>
                """
                send_email(patient.user.email, "Appointment Reminder - Hospital", html, app.config)
        
        return f"Sent reminders for {len(appointments)} appointments"

    @celery.task(name='tasks.send_monthly_report')
    def send_monthly_report():
        from backend.models import Doctor, Appointment, Treatment
        from calendar import monthrange
        
        today = date.today()
        if today.month == 1:
            report_month = 12
            report_year = today.year - 1
        else:
            report_month = today.month - 1
            report_year = today.year

        _, last_day = monthrange(report_year, report_month)
        start_date = date(report_year, report_month, 1)
        end_date = date(report_year, report_month, last_day)
        month_name = start_date.strftime('%B %Y')

        doctors = Doctor.query.all()
        for doctor in doctors:
            if not doctor.user or not doctor.user.email:
                continue

            appointments = Appointment.query.filter(
                Appointment.doctor_id == doctor.id,
                Appointment.date >= start_date,
                Appointment.date <= end_date
            ).all()

            completed = [a for a in appointments if a.status == 'Completed']
            cancelled = [a for a in appointments if a.status == 'Cancelled']

            rows = ""
            for apt in completed:
                t = apt.treatment
                rows += f"""
                <tr>
                    <td>{apt.date}</td>
                    <td>{apt.patient.full_name}</td>
                    <td>{t.diagnosis if t else '-'}</td>
                    <td>{t.prescription if t else '-'}</td>
                    <td>{t.next_visit if t else '-'}</td>
                </tr>"""

            html = f"""
            <html><body style="font-family: Arial, sans-serif;">
            <h1>Monthly Activity Report - {month_name}</h1>
            <h2>Dr. {doctor.full_name}</h2>
            <p><strong>Department:</strong> {doctor.department.name if doctor.department else 'N/A'}</p>
            <hr>
            <h3>Summary</h3>
            <ul>
                <li>Total Appointments: {len(appointments)}</li>
                <li>Completed: {len(completed)}</li>
                <li>Cancelled: {len(cancelled)}</li>
            </ul>
            <h3>Completed Appointments Detail</h3>
            <table border="1" cellpadding="8" cellspacing="0" style="border-collapse:collapse; width:100%;">
            <thead><tr>
                <th>Date</th><th>Patient</th><th>Diagnosis</th><th>Prescription</th><th>Next Visit</th>
            </tr></thead>
            <tbody>{rows}</tbody>
            </table>
            <br><p>Generated on {datetime.now().strftime('%d %B %Y')}</p>
            </body></html>
            """
            send_email(doctor.user.email, f"Monthly Activity Report - {month_name}", html, app.config)

        return f"Monthly reports sent for {len(doctors)} doctors"

    @celery.task(name='tasks.export_patient_csv')
    def export_patient_csv(patient_id, user_email):
        from backend.models import Patient, Appointment
        
        patient = Patient.query.get(patient_id)
        if not patient:
            return "Patient not found"

        appointments = Appointment.query.filter_by(
            patient_id=patient_id, status='Completed'
        ).all()

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            'Visit No', 'Patient Name', 'Doctor', 'Department',
            'Appointment Date', 'Time Slot', 'Visit Type',
            'Tests Done', 'Diagnosis', 'Prescription', 'Medicines',
            'Doctor Notes', 'Next Visit'
        ])

        for i, apt in enumerate(appointments, 1):
            t = apt.treatment
            writer.writerow([
                i,
                patient.full_name,
                apt.doctor.full_name if apt.doctor else '',
                apt.doctor.department.name if apt.doctor and apt.doctor.department else '',
                apt.date.isoformat(),
                apt.time_slot,
                apt.visit_type,
                t.tests_done if t else '',
                t.diagnosis if t else '',
                t.prescription if t else '',
                t.medicines if t else '',
                t.doctor_notes if t else '',
                t.next_visit.isoformat() if t and t.next_visit else ''
            ])

        csv_content = output.getvalue()
        
        #Send email with CSV
        html = f"""
        <html><body>
        <h2>Treatment History Export</h2>
        <p>Dear {patient.full_name},</p>
        <p>Your treatment history export is ready. Please find the CSV data below:</p>
        <pre>{csv_content}</pre>
        <p>Thank you for using our Hospital Management System.</p>
        </body></html>
        """
        send_email(user_email, "Treatment History Export", html, app.config)
        
        return {'status': 'done', 'csv': csv_content}

    return send_daily_reminders, send_monthly_report, export_patient_csv
