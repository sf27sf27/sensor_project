import time

HARDWARE_AVAILABLE = False
bme280 = None

try:
	import board
	import busio
	import adafruit_bme280.basic as adafruit_bme280
	
	# Initialize I2C
	i2c = busio.I2C(board.SCL, board.SDA)
	
	# Try to find BME280 at either address (0x77 or 0x76)
	bme280 = None
	for address in [0x77, 0x76]:
		try:
			bme280 = adafruit_bme280.Adafruit_BME280_I2C(i2c, address=address)
			break
		except ValueError:
			# This address doesn't have the device, try next
			continue
	
	if bme280 is None:
		raise ValueError("No BME280 device found at addresses 0x76 or 0x77")
	
	# Optional: set sea level pressure for altitude accuracy
	bme280.sea_level_pressure = 1013.25
	HARDWARE_AVAILABLE = True
except Exception as e:
	# Catch any exception during hardware initialization
	# This includes: ImportError, NotImplementedError, OSError, ValueError, etc.
	HARDWARE_AVAILABLE = False
	bme280 = None


def read():
	if not HARDWARE_AVAILABLE:
		return {
			"temperature": {"c": None, "f": None},
			"pressure": {"hpa": None},
			"humidity": {"rh": None},
			"error": "BME280 sensor not available on this platform"
		}
	
	try:
		t = bme280.temperature
		p = bme280.pressure
		h = bme280.humidity
		temp_data = {
			"c":round(t,2),
			"f":round(t*1.8+32,2)
		}
		pressure_data = {
			"hpa":round(p,2)
		}
		humidity_data = {
			"rh":round(h,2)
		}
		data = {
			"temperature":temp_data,
			"pressure":pressure_data,
			"humidity":humidity_data
		}
		return data
	except Exception as e:
		return {"error": str(e)}
