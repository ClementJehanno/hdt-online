#!/usr/bin/python

""" 
  A HDT converter service.

@author: Michael Hausenblas, http://mhausenblas.info/#i
@since: 2012-09-19
@status: init
"""
import sys, os, logging, getopt, StringIO, urlparse, urllib, string, cgi, time, datetime, json, shlex, subprocess, uuid
from BaseHTTPServer import BaseHTTPRequestHandler

# Configuration
DEBUG = True
SERVICE_BASE = 'localhost'
SERVICE_PORT = 6970
HDT_PATH = '/Users/michael/Documents/dev/hdt/hdt-java/'
DATA_DIR = 'data/'

base = SERVICE_BASE
port = SERVICE_PORT

if DEBUG:
	FORMAT = '%(asctime)-0s %(levelname)s %(message)s [at line %(lineno)d]'
	logging.basicConfig(level=logging.DEBUG, format=FORMAT, datefmt='%Y-%m-%dT%I:%M:%S')
else:
	FORMAT = '%(asctime)-0s %(message)s'
	logging.basicConfig(level=logging.INFO, format=FORMAT, datefmt='%Y-%m-%dT%I:%M:%S')



# the main HDT online service
class HDTOnlineServer(BaseHTTPRequestHandler):
	
	# reacts to GET request by serving static content in standalone mode and
	def do_GET(self):
		parsed_path = urlparse.urlparse(self.path)
		target_url = parsed_path.path[1:]
		
		# API calls
		if self.path.startswith('/data/'):
			self.serve_content(target_url, media_type='application/octet-stream') # ask Mario re correct media type
		# static stuff (for standalone mode - typically served by Apache or nginx)
		elif self.path == '/':
			self.serve_content('index.html')
		elif self.path.endswith('.ico'):
			self.serve_content(target_url, media_type='image/x-icon')
		elif self.path.endswith('.html'):
			self.serve_content(target_url, media_type='text/html')
		elif self.path.endswith('.js'):
			self.serve_content(target_url, media_type='application/javascript')
		elif self.path.endswith('.css'):
			self.serve_content(target_url, media_type='text/css')
		elif self.path.startswith('/img/'):
			if self.path.endswith('.gif'):
				self.serve_content(target_url, media_type='image/gif')
			elif self.path.endswith('.png'):
				self.serve_content(target_url, media_type='image/png')
			else:
				self.send_error(404,'File Not Found: %s' % target_url)
		else:
			self.send_error(404,'File Not Found: %s' % target_url)
		return
	
	# handles API calls to convert HDT to and from other RDF formats
	def do_POST(self):
		ctype, pdict = cgi.parse_header(self.headers.getheader('content-type'))
		parsed_path = urlparse.urlparse(self.path)
		target_url = parsed_path.path[1:]
		
		# deal with paramter encoding first
		if ctype == 'multipart/form-data':
			postvars = cgi.parse_multipart(self.rfile, pdict)
			logging.debug('POST to %s with multipart/form-data: %s' %(self.path, postvars))
		elif ctype == 'application/x-www-form-urlencoded':
			length = int(self.headers.getheader('content-length'))
			postvars = cgi.parse_qs(self.rfile.read(length), keep_blank_values=1)
			logging.debug('POST to %s with application/x-www-form-urlencoded: %s' %(self.path, postvars))
		else:
			postvars = {}
		
		# API calls
		if postvars and target_url == 'convert':
			inputdoc = postvars['inputdoc'][0]
			inputformat = postvars['from'][0]
			outputformat = postvars['to'][0]
			
			# case distinction, but for now only one
			
			localinputdoc = urlparse.urlparse(inputdoc).path.split('/')[-1]
			if DEBUG: logging.debug('Input document: %s' %localinputdoc)
			self.get_content(inputdoc, localinputdoc)
			outputdoc = self.turtle2HDT(localinputdoc)
			self.send_response(200)
			self.send_header('Content-type', 'application/json')
			self.end_headers()
			self.wfile.write(json.dumps({ 'outputlocation' : outputdoc }))
		else:
			self.send_error(404,'File Not Found: %s' % target_url)
		return
	
	def turtle2HDT(self, inputdoc):
		inputdoc = os.path.join(DATA_DIR, inputdoc)
		outputdoc = ''.join([str(uuid.uuid4()), '.hdt'])
		outputdoc = os.path.join(DATA_DIR, outputdoc)
		params = '%s %s' %(inputdoc, outputdoc)
		cp = ' -classpath "%sbin:%slib/*"' %(HDT_PATH, HDT_PATH)
		cmd = ''.join(['java -server -Xms1024M -Xmx1024M', cp, ' org.rdfhdt.hdt.tools.RDF2HDT ', params])
		if DEBUG: logging.debug('Calling HDT converter with:\n%s' %cmd)
		args = shlex.split(cmd)
		s = subprocess.Popen(args, stderr=subprocess.STDOUT, stdout=subprocess.PIPE).communicate()[0]
		if DEBUG: logging.debug('Result of HDT converter:\n%s' %s)
		return outputdoc
	
	# changes the default behavour of logging everything - only in DEBUG mode
	def log_message(self, format, *args):
		if DEBUG:
			try:
				BaseHTTPRequestHandler.log_message(self, format, *args)
			except IOError:
				pass
		else:
			return
	
	# serves static content from file system
	def serve_content(self, p, media_type='text/html'):
		try:
			f = open(os.curdir + os.sep + p)
			self.send_response(200)
			self.send_header('Content-type', media_type)
			self.end_headers()
			self.wfile.write(f.read())
			f.close()
			return
		except IOError:
			self.send_error(404,'File Not Found: %s' % self.path)
	
	# retrieves remote content and stores it locally
	def get_content(self, remotedoc, localdoc):
		logging.debug('GETing %s' %remotedoc)
		content = urllib.urlopen(remotedoc)
		localdoc = os.path.join(DATA_DIR, localdoc)
		if not os.path.exists(DATA_DIR):
			os.makedirs(DATA_DIR)
		ds = open(localdoc, 'w')
		ds.write(content.read())
		ds.close()

def usage():
	print("Usage: python hdt-online.py -b {base} -p {port}\n")
	print("Example: python hdt-online.py -b abc.com -p 8080")

if __name__ == '__main__':
	try:
		# extract and validate options and their arguments
		print("="*80)
		opts, args = getopt.getopt(sys.argv[1:], "hb:p:v", ["help", "base=", "port=", "verbose"])
		for opt, arg in opts:
			if opt in ("-h", "--help"):
				usage()
				sys.exit()
			elif opt in ("-b", "--base"):
				base = arg
				logging.info("Using base: %s" %base)
			elif opt in ("-p", "--port"):
				port = int(arg)
				logging.info("Using port: %s" %port)
			elif opt in ("-v", "--verbose"): 
				DEBUG = True
		print("="*80)
		from BaseHTTPServer import HTTPServer
		server = HTTPServer(('', port), HDTOnlineServer)
		logging.info('HDTOnlineServer started, use {Ctrl+C} to shut-down ...')
		server.serve_forever()
	except getopt.GetoptError, err:
		print str(err)
		usage()
		sys.exit(2)	
	
	
	
	
	
