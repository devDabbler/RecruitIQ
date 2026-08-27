from backend.utils.database import get_db
from backend.models.models import Candidate, Job

db = next(get_db())
alex = db.query(Candidate).filter(Candidate.first_name == 'Alex', Candidate.last_name == 'Jones').first()

print('Alex Jones found:', alex is not None)
if alex:
    print('Current position:', alex.current_position)
    print('Experience years:', alex.experience_years)
    print('Experience level:', alex.experience_level)
    print('Skills count:', len(alex.skills))
    print('Skills:', [s.skill_name for s in alex.skills[:10]])
    
    # Check for Senior Data Scientist job
    senior_ds_job = db.query(Job).filter(Job.title.like('%Senior Data Scientist%')).first()
    if senior_ds_job:
        print('\nSenior Data Scientist job found:', senior_ds_job.title)
        print('Job skills:', senior_ds_job.skills)
    else:
        print('\nNo Senior Data Scientist job found')
else:
    print('Alex Jones not found in database') 