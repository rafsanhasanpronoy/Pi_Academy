# Pi Academy — Educational Institute Management System

A comprehensive Django-based Educational Institute Management System designed to manage students, faculty, attendance, academic activities, payments, payroll, notices, admissions, achievements, galleries, and administrative operations through a centralized dashboard.

## Features

### Student Management
- Student profiles and academic records
- Class and batch management
- Guardian information management
- Student admission tracking

### Attendance System
- Student attendance tracking
- Faculty attendance management
- Present, Absent, and Late status support
- Attendance summaries and reports

### Faculty Management
- Faculty profiles
- Subject assignments
- Class scheduling
- Faculty activity monitoring

### Teacher Salary Management
- Monthly payroll processing
- Attendance-based deductions
- Class-based payment calculation
- Bonus and deduction support
- Salary slip generation

### Student Payment System
- Monthly fee collection
- Admission fees
- Examination fees
- Receipt generation
- Multiple payment methods support

### Academic Management
- Classes and batches
- Subjects
- Academic years
- Exam management
- Result management

### Student Result Portal
- Student result lookup
- Attendance summary
- Secure access using student credentials

### Admissions
- Admission inquiry management
- Online admission information
- Applicant tracking

### Notices and Achievements
- Notice publishing system
- Achievement management
- Public announcement pages

### Gallery Management
- Image gallery system
- Categorized media organization
- Achievement and event galleries

### Contact Management
- Public contact form
- Message management
- Inquiry tracking

## Technology Stack

| Component | Technology |
|-----------|------------|
| Backend | Django 5.2 |
| Language | Python |
| Database | PostgreSQL |
| Cloud Database | Supabase |
| Frontend | HTML, CSS, JavaScript, Django Templates |
| Web Server | Gunicorn |
| Static Files | WhiteNoise |
| Media Storage | Supabase Storage / S3 Compatible Storage |
| Cache | Redis |
| PDF Generation | ReportLab |
| Excel Support | openpyxl |

## Project Structure

```text
Pi_Academy/
├── config/
├── core/
├── templates/
├── static/
├── media/
├── manage.py
├── requirements.txt
├── Procfile
└── start.sh
```

## Installation

### Clone Repository

```bash
git clone https://github.com/rafsanhasanpronoy/Pi_Academy.git
cd Pi_Academy
```

### Create Virtual Environment

```bash
python -m venv venv
```

### Activate Environment

Windows:

```bash
venv\Scripts\activate
```

Linux/macOS:

```bash
source venv/bin/activate
```

### Install Dependencies

```bash
pip install -r requirements.txt
```

### Run Migrations

```bash
python manage.py migrate
```

### Start Development Server

```bash
python manage.py runserver
```

## Environment Variables

Example:

```env
SECRET_KEY=your-secret-key
DEBUG=True
DB_NAME=postgres
DB_USER=postgres
DB_PASSWORD=your-password
DB_HOST=your-host
DB_PORT=5432
REDIS_URL=redis://localhost:6379/1
```

## Security Features

- Django authentication
- CSRF protection
- Secure cookie support
- HTTPS support
- Environment-based secret management
- Rate limiting support
- Redis caching

## Deployment

Supported deployment platforms:

- Render
- Railway
- VPS Hosting
- Docker-compatible environments

Production server:

```bash
gunicorn config.wsgi
```

## Main Modules

- Student Management
- Faculty Management
- Attendance Management
- Teacher Salary System
- Payment Management
- Exam & Result Management
- Admissions
- Notices
- Achievements
- Gallery
- Contact System

## Developer

**Rafsan Hasan Pronay**

GitHub: https://github.com/rafsanhasanpronoy

## License

This project is maintained as an educational institute management solution. Add an open-source license if redistribution is intended.
