import os
import django
import sys

# Add the project path to the sys.path
sys.path.append('/home/ubuntu/project/titan')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'main.settings')
django.setup()

from backend.models import TblUser, TblUserLogin

def reset_attempts(email):
    try:
        user = TblUser.objects.get(email=email)
        print(f"Found user: {user.email} (ID: {user.id})")
        
        try:
            user_login = TblUserLogin.objects.get(user_id=user.id)
            print(f"Current login attempts: {user_login.attempt}")
            
            user_login.attempt = 0
            user_login.save()
            
            print(f"Successfully reset login attempts for {email} to 0.")
            
        except TblUserLogin.DoesNotExist:
            print(f"Error: TblUserLogin entry not found for user {email}.")
            
    except TblUser.DoesNotExist:
        print(f"Error: User with email {email} not found.")

if __name__ == "__main__":
    target_email = "softcan@naver.com"
    reset_attempts(target_email)
