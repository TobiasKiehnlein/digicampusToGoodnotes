import glob
import json
import os
import smtplib
import urllib
import zipfile
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.utils import COMMASPACE, formatdate
from os.path import basename

import requests
from lxml import etree

import config


def unzip(zipPath, outPath):
	print('Unzipping files....', end='\r')
	zip_ref = zipfile.ZipFile(zipPath, 'r')
	zip_ref.extractall(outPath)
	zip_ref.close()
	print('Unzipping finished')


def shouldDownload(document, course, time=""):
	if (course + document + time) in config.downloaded:
		return False
	for black in config.blacklist:
		if black in document or black in course:
			return False
	return True


__session = requests.Session()

response = __session.get(
	"https://digicampus.uni-augsburg.de/dispatch.php/start?sso=webauth&cancel_login=1&again=yes&standard=no")

data = {kv.split('=')[0]: kv.split('=')[1] for kv in urllib.parse.unquote(response.url).split('?')[-1].split(';')}
data["username"] = config.username
data["password"] = config.password
data["login"] = "yes"
data["rm"] = "index"
del data["test_cookie"]

if config.debug:
	print("{")
	for d in data:
		print("\t" + d + ": " + data[d])
	print("}")

response = __session.post("https://websso.uni-augsburg.de/login", data=data)
url = response.content.decode('latin1').split('URL=\'')[1].split('\'')[0]
__session.get(url)

response = __session.get("https://digicampus.uni-augsburg.de/dispatch.php/my_courses")

tree = etree.HTML(response.content.decode('latin1'))

r = tree.xpath('//table[contains(@class,"mycourses")]//tr/td[3]//a[contains(@href, "auswahl")]')

for i, ref in enumerate(r):

	files = []

	courseUrl = ref.attrib["href"]
	downloadUrl = "https://digicampus.uni-augsburg.de/folder.php?cid=" + courseUrl.split("auswahl=")[1] + "&cmd=all"
	response = __session.get(downloadUrl)

	if config.debug:
		with open("courses/" + courseUrl.split("auswahl=")[1] + ".html", "wb") as file:
			file.write(response.content)

	tree = etree.ElementTree(etree.HTML(response.content.decode('latin1')))

	courseName = tree.xpath('//div[@id="barBottommiddle"]')[0].text.split(" - Dateien")[0].strip()
	securityToken = tree.xpath('//input[@name="security_token"]')[0].attrib['value']
	x = tree.xpath('//div[@id="filesystem_area"]//table//div[starts-with(@id, "file_") and @class=""]')

	for element in x:
		error = False
		try:
			documentName = tree.xpath(tree.getpath(element) + '//span[starts-with(@id, "file_")]')[0].text
		except:
			documentName = ""
			print("The documentName cannot be loaded!")
			error = True
		'''try:
			documentTime = tree.xpath(tree.getpath(element) + '//td[@align="right"]/text()')[0].text
		except:
			documentTime = ""
			print("The document time cannot be loaded")'''
		try:
			documentId = tree.xpath(tree.getpath(element) + '//input[@type="CHECKBOX"]')[0].attrib['value']
		except:
			documentId = ""
			print("The documentId cannot be loaded!")
			error = True

		if not error and shouldDownload(documentName, courseName):
			files.append({'documentName': documentName, 'documentId': documentId})
			config.downloaded.append(courseName + documentName)  # + documentTime)

	with open("downloaded.json", 'w') as file:
		file.write(json.dumps(config.downloaded))

	downloadData = {"download_selected": "", "security_token": securityToken}
	downloadData.update({'download_ids[%s]' % i: d['documentId'] for i, d in enumerate(files)})
	response = __session.post(downloadUrl, data=downloadData, stream=True)

	with open(config.out + "/" + courseName, 'wb') as handle:
		for chunk in response.iter_content(chunk_size=config.chunkSize):
			if chunk:
				handle.write(chunk)

	try:
		unzip(config.out + "/" + courseName, config.out + "/final/" + courseName + "/")
	except:
		print("File cannot be unzipped!", courseName)

# Send files to email Adress
print("Connecting to server...")
server = smtplib.SMTP(config.emailServer, 587)

# Next, log in to the server
print("Starting ssl...")
server.starttls()
print("Logging in...")
server.login(config.email, config.emailPassword)

print("Send mails...")

count = 0

for filename in glob.iglob('./downloads/final/**', recursive=True):
	if os.path.isfile(filename):  # filter dirs
		if filename.endswith(".pdf"):
			# Send the mail
			msg = MIMEMultipart()
			msg['From'] = config.sender
			msg['To'] = COMMASPACE.join(config.to)
			msg['Date'] = formatdate(localtime=True)
			msg['Subject'] = filename

			with open(filename, "rb") as fil:
				part = MIMEApplication(
					fil.read(),
					Name=basename(filename)
				)
			# After the file is closed
			part['Content-Disposition'] = 'attachment; filename="%s"' % (
					os.path.basename(os.path.dirname(filename)) + '/' + basename(filename))
			msg.attach(part)
			server.sendmail(config.sender, config.to, msg.as_string())
			count += 1
			print("\tFile send: " + "\t" + filename)
		os.remove(filename)

print(str(count) + " Dateien wurden versendet!")
