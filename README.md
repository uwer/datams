# datams

## Installation (Ubuntu OS)

---
*NOTE:*
- Replace `ubuntu` username with your actual username in the directions below

---

### 1. Install the dependancies
```bash
    sudo add-apt-repository ppa:deadsnakes/ppa
    sudo apt update
    sudo apt install software-properties-common
    sudo apt install python3.10 python3.10-distutils python3.10-dev python3.10-venv python3-pip
    sudo apt install libpq-dev build-essential
    sudo apt install libgl1-mesa-glx
    sudo apt install postgresql
    sudo apt install redis
    sudo apt install nginx
```

### 2. Install and setup scripts for virtual environment
```bash
    python3.10 -m pip install --upgrade pip
    python3.10 -m pip install virtualenvwrapper
    export PATH="/home/ubuntu/.local/bin:$PATH"
    export VIRTUALENVWRAPPER_PYTHON=/usr/bin/python3.10
```

### 3. Pull the source code from the repository

```bash
    git clone git@github.com:MaxGunton/datams.git  # get source code from git
    sudo mv datams /usr/local/src
    export WORKON_HOME=/usr/local/src/datams/.venv
    mkdir -p $WORKON_HOME
```
   

### 4. Run the virtualenvwrapper scripts
```bash
    source /home/ubuntu/.local/bin/virtualenvwrapper.sh
```

If this is not the correct location then it can be found using
```bash
    pip show -f virtualenvwrapper
```

---
*NOTE:*
- These export commands (and the virtualenvwrapper script) can be added to .bashrc (so they will run on login)

---

### 5. Make the virtual environment and install the required dependancies including our package
```bash
    mkvirtualenv -p python3.10 datams
    pip install -r /usr/local/src/datams/requirements.txt
```

### 6. Create the new database
```bash
    sudo -u pstgres createdb datams
```

### 7. Log into postgres database as postgres user and create datams user and grant them priviledges on the new database
```bash
    sudo -u postgres psql
    postgres=# CREATE USER datams WITH encrypted PASSWORD '<password>';  # remember this password
    postgres=# GRANT ALL PRIVILEGES ON DATABASE datams TO datams;
    postgres=# exit;
```

### 8. Add passwords to the configuration file
```
    python -c 'import secrets; print(secrets.token_hex())'  # remember this key
    nano /usr/local/src/datams/datams/config.yml  # replace dummy passwords with real ones
```

### 9. Set up nginx with our web app
```bash
    sudo mv /usr/local/src/datams/installation/datams /etc/nginx/sites-available/  # move our site config
    sudo chown root:root /etc/nginx/sites-available/datams
    sudo chmod 644 /etc/nginx/sites-available/datams
    sudo ln -s /etc/nginx/sites-available/datams /etc/nginx/sites-enabled/
    sudo rm /etc/nginx/sites-enabled/default
    sudo nano /etc/nginx/nginx.conf 
        # change line `user www-data;` to `user ubuntu;`
        # add the following to http section: 
            # set client body size to 4MB #
            client_max_body_size 4M;
```

### 10. Set up gunicorn service to run under supervision of systemd (change user dictated by gunicorn.service to you're username)
```
  sudo mv /usr/local/src/datams/installation/gunicorn.service /etc/systemd/system/
  sudo chown root:root /etc/systemd/system/gunicorn.service
  sudo chmod 644 /etc/systemd/system/gunicorn.service
```

### 11. Set up celery service to run under supervision of systemd (change user dictated by celery.service to you're username)
```bash
    sudo mv /usr/local/src/datams/installation/celery.service /etc/systemd/system/
    sudo chown root:root /etc/systemd/system/celery.service
    sudo chmod 644 /etc/systemd/system/celery.service
```

### 12. Restart the systemd daemon to reflect the changes
```bash
    sudo systemctl daemon-reload
```

### 13. Initialize the database
```bash
    flask --app /usr/local/src/datams/ init-db
```

### 14. Prime the database with initial values
- TODO: Come up with strategy for this

### 15. Change the priviledges on the web-app source (to protect private keys etc.) and create required directories
```bash
  sudo chmod -R o-rwx /usr/local/src/datams/
  sudo mkdir -p /var/lib/datams/uploads/submitted
  sudo mkdir -p /var/lib/datams/uploads/pending
  sudo chmod -R 770 /var/lib/datams
```

### 16. start services and check their status to ensure they started correctly
```bash
    sudo systemctl start celery
    sudo systemctl status celery
    sudo systemctl start gunicorn
    sudo systemctl status gunicorn
    sudo systemctl restart nginx
```

### Other
- TODO: HOW TO GET GOOGLE API KEY?
- TODO: SET UP BACKUP OF POSTGRES
- TODO: CONTAINERIZE


## TODO

### Essential Requirements
   - Come up with a strategy for how to load the files in initially?
   - ensure gunicorn, nginx, redis, and celery .service files include that these service should automatically restart after failures (make sure to look at common pitfuls for these)
   - ssl certificate for nginx (and add details to config)
   - user template(s)
   - user function (change_password, reset_password/forgot_password)
   - admin template(s)
   - admin functions (remove_user, invite_user, change_user_priviledges (except to other admins))
   - figure out mail server and set-up with flask-mail using postfix and Dovecot?
   - add email password reset feature using flask-login by implementing @login_manager.request_loader
   - create an npm? environment for the web development kits used (datatables, bootstrap5, ...)
   - add flash block to main or base template at the top and have status information and errors flashed
     to user through this mechanism
   - catch database errors in view methods that call them and flash these to the user.  
   - cronjob to dump database daily in-case of catastrophic loss
   - implement logging in flask application
   - add functionality to add/remove files from organization, deployment, and mooring edit views.  
   - have failed transactions rollback by executing them all in a block instead of separately
   - a set of tests suite
   - Fix the error involving letter case of uploads filenames (could force lowercase)
   
### Non-essential Requirements
   - add constraint that comma's aren't allowed in any strings stored in the database because it is currently assumed but not enforced
   - sort menu lists before sending to templates so that they are in the correct order
   - avoid showing none/na by using .fillna('') on dataframe before sending to templates
   - make the general sections of the edit templates simply use a prefilled version of the add templates, but for the file.edit template make sure to remove the option to drop files.  
   - format page templates for better layout and presentation of data
   - have the file.details template show a preview of the file and ensure that the file doesn't automatically download
   - enable mass updates on files (like changing a bunch from owned by a deployment to owned by a piece of mooring equipment)
   - within the database a set tables which would allow admin to rollback database to any specific time
   - implement client side form validation where possible and have things like latitude and longitude round to nearest valid value when entered
   - make additional background task called update_cache which only changes the relevant rows instead of recomputing the entire dataframe
   - When editing or unlinking prompt user with a confirmation message before commiting any changes, also prompt user with message when navigating away
   - Generate banner title in the views.py
   - Create a component for buttons (i.e. add, delete, edit) could be a single component that is given options, and send that to banner template with title (i.e. Do away with the banner button stuff and create a component that can be added to the banner view same for title)
   - replace forms so they are implemented using WTF-Flask
   - use Flask-Upload to handle file uploads?
   - look into using an implementation of the merkle tree for the stored file uploads to ensure data-consistency
   - decide on set of file descriptions
   - Add typing hints where they are missing
   - create themed pages for displaying http codes (i.e. 404, 300)
   - implment viewer priviledges by creating custom decorating similar to the @login_required decorated
     that checks if user.role < 2.  Also should disable or hide the buttons to access these areas from this type of user
   - table to log user actions to see how system is being used