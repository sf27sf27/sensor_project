import subprocess

def read():
	try:
		output = subprocess.check_output(
		["vcgencmd", "measure_temp"]
		).decode()
		c_output = round(float(output.strip().split("temp=")[1].split("'")[0]),2)
		f_output = round(c_output*1.8+32,2)
		data = {
			"c" : c_output,
			"f" : f_output
		}

		return data
	except Exception:
		return "Error"

