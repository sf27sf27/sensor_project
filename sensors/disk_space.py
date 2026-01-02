
import shutil

def bytes_to_mb(b):
	return round(b / (1024**2), 2)

def read():
	try:
		output = shutil.disk_usage("/")
		total = output.total
		used = output.used
		free = output.free
		data = {
			"total_mb": bytes_to_mb(total),
			"used_mb": bytes_to_mb(used),
			"free_mb": bytes_to_mb(free)
		}
		return data
	except Exception as e:
		return {"error": str(e)}

