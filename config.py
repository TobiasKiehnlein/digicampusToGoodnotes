import json

configData = {}

with open('config.json') as file:
	configData = json.loads(file.read())

with open('downloaded.json') as downloadedFile:
	try:
		downloaded = json.loads(downloadedFile.read())
	except:
		downloaded = []


def __getattr__(name):
	if name in configData:
		return configData[name]
	return None
