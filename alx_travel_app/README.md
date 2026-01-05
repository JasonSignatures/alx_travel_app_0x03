"""markdown
# ALX Travel App - Phase 0: Database Modeling and Data Seeding

A small Django application demonstrating database modeling, API serialization, and data seeding for travel listings, bookings, and reviews.

## Quick Start (Windows / PowerShell)

1. Clone the repository:
   ```powershell
   git clone <repo-url> alx_travel_app_0x01
   cd alx_travel_app_0x01
   ```

2. Create and activate a virtual environment:
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

3. Install dependencies:
   ```powershell
   pip install -r requirements.txt
   ```

4. Apply database migrations:
   ```powershell
   cd alx_travel_app
   python manage.py migrate
   ```

5. (Optional) Seed the database (project includes `listings/management/commands/seed.py`):
   ```powershell
   python manage.py seed
   ```

6. Run the development server:
   ```powershell
   python manage.py runserver
   ```

## Project structure

- `alx_travel_app/` — Django project settings and config
- `listings/` — App with models, serializers, views, tests, and management commands
- `requirements.txt` — Python dependencies

## Contributing

1. Create a branch:
   ```powershell
   git checkout -b feat/update-readme
   ```
2. Make changes, commit, push, then open a pull request.

## License

See `LICENSE` in the repository root.

"""
# ALX Travel App - Phase 0: Database Modeling and Data Seeding

This project is a Django application for managing travel listings, bookings, and reviews.  
It demonstrates **database modeling**, **API serialization**, and **data seeding**.

---

## Table of Contents

- [Project Setup](#project-setup)
- [Models](#models)
- [Serializers](#serializers)
- [Database Seeding](#database-seeding)
- [Usage](#usage)

---

## Project Setup

1. Clone or duplicate the project:

```bash
cp -r alx_travel_app alx_travel_app_0x00
cd alx_travel_app_0x00

Lets do this

## Chapa Payment Integration (listings)

### Env vars
- CHAPA_SECRET_KEY: your Chapa secret key (test or live)

### Endpoints
- POST /listings/chapa/init/  -> initialize payment, returns checkout_url
- GET  /listings/chapa/verify/<tx_ref>/ -> verify payment and update Payment model
- GET  /listings/chapa/callback/ -> callback handler (Chapa calls this)

### Testing
- Use Chapa sandbox keys (developer.chapa.co)
- Expose local server with ngrok to receive callbacks
- Example init curl request: see docs above

### Tasks
- Make sure Celery is running to send confirmation emails
### Log: payment init success
INFO django.request: "POST /listings/chapa/init/ HTTP/1.1" 201 -
DEBUG listings.views: Chapa init response: {'status': 'success', 'message': 'Hosted Link', 'data': {'checkout_url': 'https://checkout.chapa.co/checkout/payment/Od4P12hbhk...', 'ref_id': 'APqDvYw1okk2', 'tx_ref': 'booking-3f9a1a2bff'}}

### log: verify success
INFO listings.views: Verifying tx_ref booking-3f9a1a2bff
INFO listings.views: Chapa verify response: {'status':'success','message':'Transaction Found','data':{'status':'success','ref_id':'APqDvYw1okk2','tx_ref':'booking-3f9a1a2bff','amount':1000}}
INFO listings.tasks: queued send_payment_confirmation_email for Payment(id=7)
 
