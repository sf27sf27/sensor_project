import time

try:
	import board
	import busio
	import adafruit_bme280.basic as adafruit_bme280
	HARDWARE_AVAILABLE = True
	
	# Initialize I2C
	i2c = busio.I2C(board.SCL, board.SDA)
	
	# If address is 0x76 (most common)
	bme280 = adafruit_bme280.Adafruit_BME280_I2C(i2c, address=0x77)
	
	# Optional: set sea level pressure for altitude accuracy
	bme280.sea_level_pressure = 1013.25
except (NotImplementedError, ImportError):
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
