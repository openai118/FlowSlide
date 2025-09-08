("""Clear application tables in the external database.

This script will connect to the external DATABASE_URL from .env and TRUNCATE
all tables defined in the application's SQLAlchemy metadata using CASCADE.

To avoid accidental destructive runs, the script requires the environment
variable `CONFIRM_CLEAR` to be set to `yes` before it will execute the
TRUNCATE statements. Without that it will print the tables and exit.
""")

import os
from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import create_engine, text

def main():
	db_url = os.getenv('DATABASE_URL')
	if not db_url:
		print('No DATABASE_URL configured in environment; aborting')
		return

	# Use psycopg2 sync driver
	if db_url.startswith('postgresql+asyncpg://'):
		sync_url = db_url.replace('postgresql+asyncpg://', 'postgresql+psycopg2://')
	elif db_url.startswith('postgresql://') and '+psycopg2' not in db_url:
		sync_url = db_url.replace('postgresql://', 'postgresql+psycopg2://')
	else:
		sync_url = db_url

	print('Target DB URL (sync):', sync_url)

	# Import models metadata
	try:
		from src.flowslide.database.models import Base
	except Exception as e:
		print('Failed to import Base metadata:', e)
		return

	# Build list of table names from metadata
	table_names = [t.name for t in reversed(Base.metadata.sorted_tables)]

	print('\nThe following tables will be truncated (in order):')
	for t in table_names:
		print(' -', t)

	confirm = os.getenv('CONFIRM_CLEAR', '').lower()
	if confirm != 'yes':
		print('\nTo actually perform the destructive clear, set CONFIRM_CLEAR=yes and re-run.')
		return

	engine = create_engine(sync_url, pool_pre_ping=True)
	with engine.begin() as conn:
		# Use TRUNCATE ... CASCADE to handle FK dependencies
		for t in table_names:
			try:
				stmt = text(f'TRUNCATE TABLE "{t}" CASCADE')
				conn.execute(stmt)
				print(f'Truncated {t}')
			except Exception as e:
				print(f'Failed to truncate {t}:', e)

	print('\nExternal database cleared (tables truncated).')

if __name__ == '__main__':
	main()

