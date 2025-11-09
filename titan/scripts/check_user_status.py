import os
import django
import sys

# Add the project path to the sys.path
sys.path.append('/home/ubuntu/project/titan')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'main.settings')
django.setup()

from backend.models import TblUser, TblUserLogin

def check_user_status(email):
    try:
        user = TblUser.objects.get(email=email)
        print(f"--- User Status for {email} ---")
        print(f"User ID: {user.id}")
        print(f"Is Active: {user.is_active} (1 means active, 0 means inactive)")
        
        try:
            user_login = TblUserLogin.objects.get(user_id=user.id)
            print(f"Login Attempts: {user_login.attempt}")
            
        except TblUserLogin.DoesNotExist:
            print(f"TblUserLogin entry not found for user {email}.")
            
    except TblUser.DoesNotExist:
        print(f"User with email {email} not found.")
    print("---------------------------------")

if __name__ == "__main__":
    target_email = "softcan@naver.com"
    check_user_status(target_email)
