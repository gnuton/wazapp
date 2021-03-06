'''
Copyright (c) 2012, Tarek Galal <tarek@wazapp.im>

This file is part of Wazapp, an IM application for Meego Harmattan platform that
allows communication with Whatsapp users

Wazapp is free software: you can redistribute it and/or modify it under the 
terms of the GNU General Public License as published by the Free Software 
Foundation, either version 2 of the License, or (at your option) any later 
version.

Wazapp is distributed in the hope that it will be useful, but WITHOUT ANY 
WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A 
PARTICULAR PURPOSE. See the GNU General Public License for more details.

You should have received a copy of the GNU General Public License along with 
Wazapp. If not, see http://www.gnu.org/licenses/.
'''
import os
from Yowsup.Contacts.contacts import WAContactsSyncRequest
from Registration.registrationhandler import async
from PySide import QtCore
from PySide.QtCore import QObject, QUrl, QFile, QIODevice
from PySide.QtGui import QImage
from QtMobility.Contacts import *
from QtMobility.Versit import *
from constants import WAConstants
from wadebug import WADebug;
import sys
from waimageprocessor import WAImageProcessor
from accountsmanager import AccountsManager

class ContactsSyncer(QObject):
	'''
	Interfaces with whatsapp contacts server to get contact list
	'''
	contactsRefreshSuccess = QtCore.Signal(str,dict);
	contactsRefreshFail = QtCore.Signal();
	contactsSyncStatus = QtCore.Signal(str);

	def __init__(self,store, contactsManager, mode,userid = None):
		WADebug.attach(self);
		self.store = store;
		self.mode = mode
		self.uid = userid;
		
		super(ContactsSyncer,self).__init__();
		
		acc = AccountsManager.getCurrentAccount();
		
		if not acc:
			self.contactsRefreshFail.emit()
			
		
		username = str(acc.username)
		password = acc.password
		
		self.contactsManager = contactsManager
			
		self.syncer = WAContactsSyncRequest(username, password, [])	
		
	def sync(self):
		self._d("INITiATING SYNC")
		self.contactsSyncStatus.emit("GETTING");

		if self.mode == "STATUS":
			self.uid = "+" + self.uid
			self._d("Sync contact for status: " + self.uid)
			self.syncer.setContacts([self.uid])

		elif self.mode == "SYNC":
			
			phoneContacts = self.contactsManager.getPhoneContacts();
			contacts = []
			for c in phoneContacts:
				for number in c[2]:
					try:
						contacts.append(str(number))
					except UnicodeEncodeError:
						continue
			
			self.syncer.setContacts(contacts)


		self.contactsSyncStatus.emit("SENDING");
		result = self.syncer.send()
		
		if result:
			print("DONE!!")
			self.updateContacts(result["c"]);
		else:
			self.contactsRefreshFail.emit();
		
		
		
	def updateContacts(self, contacts):
		#data = str(data);
	
		if self.mode == "STATUS":
			for c in contacts:
				
				
				if not c['w'] == 1:
					continue

				status = c["s"];
				
				jid = "%s@s.whatsapp.net" % c['n']
				status = c["s"]#.encode('utf-8')

				contact = self.store.Contact.getOrCreateContactByJid(jid)
				contact.status = status.encode("unicode_escape")
				contact.save()

				self.contactsRefreshSuccess.emit(self.mode, contact);

		else:
			for c in contacts:
				self.contactsSyncStatus.emit("LOADING");
				
				if not c['w'] == 1:
					continue
				
				jid = "%s@s.whatsapp.net" % c['n']
				status = c["s"].encode("unicode_escape")
				#number = str(c["p"])
				
				contact = self.store.Contact.getOrCreateContactByJid(jid)
				contact.status = status
				contact.iscontact = "yes"
				contact.save()

			self.contactsRefreshSuccess.emit(self.mode, {});	

		
	def onRefreshing(self):
		self.start();

	@async
	def start(self):
		try:
			self.sync();
		except:
			self._d(sys.exc_info()[1])
			self.contactsRefreshFail.emit()
		#self.exec_();

class WAContacts(QObject):

	refreshing = QtCore.Signal();
	contactsRefreshed = QtCore.Signal(str,dict);
	contactsRefreshFailed = QtCore.Signal();
	contactsSyncStatusChanged = QtCore.Signal(str);
	contactUpdated = QtCore.Signal(str);
	contactPictureUpdated = QtCore.Signal(str);
	contactAdded = QtCore.Signal(str);
	contactExported = QtCore.Signal(str,str);

	def __init__(self,store):
		super(WAContacts,self).__init__();
		self.store = store;
		self.contacts = [];
		self.raw_contacts = None;
		self.manager = ContactsManager();
		self.imageProcessor = WAImageProcessor();
		
		self.syncer = ContactsSyncer(self.store, self, "SYNC");
		
		self.syncer.contactsRefreshSuccess.connect(self.contactsRefreshed);
		self.syncer.contactsRefreshFail.connect(self.contactsRefreshFailed);
		self.syncer.contactsSyncStatus.connect(self.contactsSyncStatusChanged);
		
		
	
	def initiateSyncer(self, mode, userid):
		self.syncer.mode = mode
		self.syncer.uid = userid

	def resync(self, mode, userid=None):
		self.initiateSyncer(mode, userid);
		self.refreshing.emit();
		self.syncer.start();
		
		
	def updateContact(self,jid):
		#if "@g.us" in jid:
		#	user_img = QImage("/opt/waxmppplugin/bin/wazapp/UI/common/images/group.png")
		#else:
		#	user_img = QImage("/opt/waxmppplugin/bin/wazapp/UI/common/images/user.png")

		jname = jid.replace("@s.whatsapp.net","").replace("@g.us","")
		if os.path.isfile(WAConstants.CACHE_CONTACTS + "/" + jname + ".jpg"):
			user_img = QImage(WAConstants.CACHE_CONTACTS + "/" + jname + ".jpg")
			
			user_img.save(WAConstants.CACHE_PROFILE + "/" + jname + ".jpg", "JPEG")
		
			self.imageProcessor.createSquircle(WAConstants.CACHE_CONTACTS + "/" + jname + ".jpg", WAConstants.CACHE_CONTACTS + "/" + jname + ".png")
			self.contactPictureUpdated.emit(jid);

	def checkPicture(self, jname, sourcePath):

		sourcePath = str(sourcePath)
		if os.path.isfile(WAConstants.CACHE_CONTACTS + "/" + jname + ".jpg"):
			#Don't overwrite if profile picture exists
			if os.path.isfile(WAConstants.CACHE_PROFILE + "/" + jname + ".jpg"):
				return
			user_img = WAConstants.CACHE_CONTACTS + "/" + jname + ".jpg"
		else:
			if os.path.isfile(WAConstants.CACHE_PROFILE + "/" + jname + ".jpg"):
				os.remove(WAConstants.CACHE_PROFILE + "/" + jname + ".jpg")
			user_img = sourcePath.replace("file://","")

		self.imageProcessor.createSquircle(user_img, WAConstants.CACHE_CONTACTS + "/" + jname + ".png")

		if os.path.isfile(WAConstants.CACHE_CONTACTS + "/" + jname + ".jpg"):
			os.remove(WAConstants.CACHE_CONTACTS + "/" + jname + ".jpg")

	def getContacts(self):
		contacts = self.store.Contact.fetchAll();
		if len(contacts) == 0:
			print "NO CONTACTS FOUNDED IN DATABASE"
			#self.resync();
			return contacts;		
		#O(n2) matching, need to change that
		cm = self.manager
		phoneContacts = cm.getContacts();
		tmp = []
		self.contacts = {};

		for wc in contacts:
			jname = wc.jid.replace("@s.whatsapp.net","")
			founded = False
			myname = ""
			picturePath = WAConstants.CACHE_CONTACTS + "/" + jname + ".png";
			for c in phoneContacts:
				if wc.number[-8:] == c['number'][-8:]:
					founded = True
					if c['picture']:
						self.checkPicture(jname,c['picture'] if type(c['picture']) == str else c['picture'].toString())

					c['picture'] = picturePath if os.path.isfile(picturePath) else None;
					myname = c['name']
					wc.setRealTimeData(myname,c['picture'],"yes");
					QtCore.QCoreApplication.processEvents()
					break;

			if founded is False and wc.number is not None:
				#self.checkPicture(jname,"")
				myname = wc.pushname.decode("utf8") if wc.pushname is not None else ""
				mypicture = picturePath if os.path.isfile(picturePath) else None;
				wc.setRealTimeData(myname,mypicture,"no");

			if wc.status is not None:
				wc.status = wc.status.decode("unicode_escape")
			if wc.pushname is not None:
				wc.pushname = wc.pushname.decode('utf-8');

			if wc.name is not "" and wc.name is not None:
				#print "ADDING CONTACT : " + myname
				tmp.append(wc.getModelData());
				self.contacts[wc.number] = wc;


		if len(tmp) == 0:
			print "NO CONTACTS ADDED!"
			return []

		print "TOTAL CONTACTS ADDED FROM DATABASE: " + str(len(tmp))
		self.store.cacheContacts(self.contacts);
		return sorted(tmp, key=lambda k: k['name'].upper());



	def getPhoneContacts(self):
		cm = self.manager
		phoneContacts = cm.getPhoneContacts();
		tmp = []

		for c in phoneContacts:
			wc = [];
			c['picture'] = QUrl(c['picture']).toString().replace("file://","")
			wc.append(c['name'])
			#wc.append(c['id'])
			wc.append(c['picture'])
			wc.append(c['numbers'])
			if ( len(c['numbers'])>0):
				tmp.append(wc);
		return sorted(tmp)



	def exportContact(self, jid, name):
		cm = self.manager
		phoneContacts = cm.getQtContacts();
		contacts = []

		for c in phoneContacts:
			if name == c.displayLabel():
				if os.path.isfile(WAConstants.CACHE_CONTACTS + "/" + name + ".vcf"):
					os.remove(WAConstants.CACHE_CONTACTS + "/" + name + ".vcf")
				print "founded contact: " + c.displayLabel()
				contacts.append(c)
				openfile = QFile(WAConstants.VCARD_PATH + "/" + name + ".vcf")
				openfile.open(QIODevice.WriteOnly)
				if openfile.isWritable():
					exporter = QVersitContactExporter()
					if exporter.exportContacts(contacts, QVersitDocument.VCard30Type):
						documents = exporter.documents()
						writer = QVersitWriter()
						writer.setDevice(openfile)
						writer.startWriting(documents)
						writer.waitForFinished()
				openfile.close()
				self.contactExported.emit(jid, name);
				break;



class ContactsManager(QObject):
	'''
	Provides access to phone's contacts manager API
	'''
	def __init__(self):
		super(ContactsManager,self).__init__();
		self.manager = QContactManager(self);
		self.contacts = []

	def getContacts(self):
		'''
		Gets all phone contacts
		'''
		contacts = self.manager.contacts();
		self.contacts = []
		for contact in contacts:
			avatars = contact.details(QContactAvatar.DefinitionName);
			avatar = QContactAvatar(avatars[0]).imageUrl() if len(avatars) > 0 else None;
			label =  contact.displayLabel();
			numbers = contact.details(QContactPhoneNumber.DefinitionName);

			for number in numbers:
				n = QContactPhoneNumber(number).number().replace("(", "").replace(")", "").replace(" ", "").replace("-", "")
				self.contacts.append({"alphabet":label[0].upper(),"name":label,"number":n,"picture":avatar});

		return self.contacts;


	def getPhoneContacts(self):
		contacts = self.manager.contacts();
		self.contacts = []
		for contact in contacts:
			avatars = contact.details(QContactAvatar.DefinitionName);
			avatar = QContactAvatar(avatars[0]).imageUrl() if len(avatars) > 0 else None;
			label =  contact.displayLabel();
			numbers = contact.details(QContactPhoneNumber.DefinitionName);
			allnumbers = []
			
			allnumbers = map(lambda n: QContactPhoneNumber(n).number().replace("(", "").replace(")", "").replace(" ", "").replace("-", ""), numbers   )
			
			#for number in numbers:
			#	allnumbers.append(QContactPhoneNumber(number).number())

			self.contacts.append({"name":label,"numbers":allnumbers,"picture":avatar});

		return self.contacts;


	def getQtContacts(self):
		return self.manager.contacts();