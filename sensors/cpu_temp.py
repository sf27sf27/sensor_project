import subprocess
import re

def read():
	try:
		output = subprocess.check_output(
		["vcgencmd", "measure_temp"]
		).decode().strip()
		# Parse output like "temp=52.3'C" with regex
		match = re.search(r"temp=([\d.]+)", output)
		if not match:
			return {"error": "Unable to parse temperature output"}
		c_output = round(float(match.group(1)), 2)
		f_output = round(c_output * 1.8 + 32, 2)
		data = {
			"c": c_output,
			"f": f_output
		}
		return data
	except Exception as e:
		return {"error": str(e)}

