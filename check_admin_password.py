import sys
sys.path.append('src')

from flowslide.database.database import get_db
from flowslide.database.models import User
from sqlalchemy.orm import Session

# Check admin user password hash
print('Checking admin user password hash...')
try:
    db: Session = next(get_db())

    admin_user = db.query(User).filter(User.username == 'admin').first()
    if admin_user:
        print(f'Admin user found:')
        print(f'  Username: {admin_user.username}')
        print(f'  Password hash: {admin_user.password_hash[:50]}...')
        print(f'  Is active: {admin_user.is_active}')
        print(f'  Is admin: {admin_user.is_admin}')

        # Test password verification
        test_password = 'admin123456'
        is_valid = admin_user.check_password(test_password)
        print(f'  Password "admin123456" valid: {is_valid}')

        # Try different password
        test_password2 = 'admin123'
        is_valid2 = admin_user.check_password(test_password2)
        print(f'  Password "admin123" valid: {is_valid2}')

    else:
        print('Admin user not found!')

    db.close()

except Exception as e:
    print(f'Database error: {e}')
