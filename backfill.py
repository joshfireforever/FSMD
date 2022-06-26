import os
from os import _exit, environ
import yaml
import scipy.stats as stats
from datetime import datetime
from datetime import timedelta
import time

def read_configuration():
    """
    Read configuration from the environmental variable PDG_PATH.
    """
    # TODO validate the yaml
    if "PDG_CONFIG" in environ:
        path = environ["PDG_CONFIG"]
    else:
        path = "config.yml"
    config = yaml.safe_load(open(path))
    return config
    
def get_times(data):
	historical_range = data["historical_range_hours"]
	interval_hours = data["interval_hours"]
	starting_hour = data["starting_hour"]

	current_hour = starting_hour
	times_of_day = []

	while current_hour < 24:
		times_of_day.append(current_hour)
		current_hour = current_hour + interval_hours

	now = datetime.now()
	now_hours = datetime(now.year,now.month,now.day,now.hour)

	starting_time = now_hours - timedelta(hours=historical_range)

	current_time = starting_time
	times = []
	times_epoch = []

	while current_time < now:
		if (current_time.hour in times_of_day):
			times.append(current_time)
			current_time = current_time + timedelta(hours=interval_hours)
		else:
			current_time = current_time + timedelta(hours=1)

	for time in times:
		epoch = (time - datetime(1970,1,1)).total_seconds()
		times_epoch.append(epoch)

	return times_epoch
	
backfill_file = open("backfill.txt", "w")
data = read_configuration()
times_epoch = get_times(data)
num_instances = len(times_epoch)

for metric in data["config"]:
	met_name = metric['name']
	met_desc = metric['description']
	met_type = metric['type']
	
	backfill_file.write(f"# TYPE {met_name} {met_type}\n")
	backfill_file.write(f"# HELP {met_name} {met_desc}\n")
	for sequence in metric["sequence"]:
	
		med = sequence["median"]
		stddev = sequence["standard_deviation"]
		mmin = sequence["minimum"]
		mmax = sequence["maximum"]

		# random value from median and standard deviation
		dist = stats.truncnorm((mmin - med) / stddev, (mmax - med) / stddev, loc=med, scale=stddev)
		values = dist.rvs(num_instances)
		
		for x in range(num_instances):
			backfill_file.write(f"{met_name} {values[x]} {times_epoch[x]}\n")

backfill_file.write(f"# EOF")
backfill_file.close()

print("Backfill file created at backfill.txt.")
print("Copying to prometheus container...")
os.system("docker cp backfill.txt prometheus:/prometheus/backfill.txt")
print("Loading as tsdb into prometheus...")
os.system("docker exec -it prometheus promtool tsdb create-blocks-from openmetrics backfill.txt")

time.sleep(3)

print("Restarting prometheus...")
os.system("docker restart prometheus")