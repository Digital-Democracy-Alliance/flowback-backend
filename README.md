# Flowback Backend


The flowback backend is baded on the python django package.

### Install

After cloning this repo, create a virtual environment:

```
cd flowback-backend
python -m venv env
source env/bin/activate
```

Then install the requirements:

```
pip install -r requirements.txt
```

### 

### Setup

Add your DJANGO_SECRET to environmental variables

#### Apply migrations 

```
python manage.py migrate
```

#### Create a superuser

```
python manage.py createsuperuser
```

*Note: remember these details to sign into the admin portal*

### Running

When starting up the backend be sure you have activated the virtual environment:

```
source env/bin/activate
```

Run the server:

```
python manage.py runserver
```

### Endpoints

- `admin`
- `swagger`
- `redoc`
- `api/v1`
- `media`

### Admin

Go to your local endpoint:

```
http://127.0.0.1:8000/admin
```

and log in.

