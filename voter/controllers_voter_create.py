from voter.models import VoterManager


def create_dev_user():
    first_name = "Sean"
    last_name = "Quinn"
    email = "seanquinn917@gmail.com"
    password = "Quinelakis920!!"
    allow_create = True
    # To set up this user in the database:
    # 1. Enter your information above.
    # 2. Uncomment the "VoterManager().create_developer..." line below
    # 3. Visit http://localhost:8000/voter/create_dev_user or https://wevotedeveloper.com:8000/voter/create_dev_user
    VoterManager().create_developer(first_name, last_name, email, password)
    return
