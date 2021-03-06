from .config import import_config
from .parsers import load_parser
from .deepmerge import deep_merge
from . import errors
import os
import os.path
import logging
import sys
import traceback
import shutil
import hashlib
import json
import glob
import re

try:
	import simplejson as json
except:
	pass

logger = logging.getLogger(__name__)

def organize(options):
	config = import_config(options['config'])
	default_settings = config.get('default_settings', {})
	override_settings = config.get('override_settings', {})
	for settings in config['sets']:
		comb_settings = dict(default_settings)
		deep_merge(comb_settings, settings)
		deep_merge(comb_settings, override_settings)
		if options['set_name'] == None or options['set_name'] == settings['name']:
			organize_set(options, comb_settings)

def organize_set(options, settings):
	logger.info("Beginning to organize %s"%(settings['name'],))
	prepare_for_organization(settings)
	processed_files = load_progress(settings)
	if len(processed_files) == 0:
		start_progress(settings)
	else:
		logger.info("Resuming progress after %s items"%(len(processed_files)))

	regex = None
	if 'regex' in settings:
		regex = re.compile(settings['regex'])
	omitted_dirs = generate_omitted_dirs(settings)
	files = os.listdir(settings['sourceDir'])
	files = sorted(files)
	if settings['scanMode'] in ['directories', 'files', 'toplevel']:
		for name in files:
			if name in processed_files:
				continue
			path = os.path.join(settings['sourceDir'], name)
			if path in omitted_dirs:
				continue
			if settings['scanMode'] != 'toplevel':
				if settings['scanMode'] == 'directories' and \
				   not os.path.isdir(path):
					continue
				if settings['scanMode'] == 'files' and \
				   not os.path.isfile(path):
					continue
			if regex and not regex.search(path):
				continue
			organize_item(options, settings, name)
			add_progress(settings, name)
	finish_progress(settings)

def organize_item(options, settings, name):
	metadata = load_item_metadata(options, settings, name)
	do_output(options, settings, metadata)

def load_item_metadata(options, settings, name):
	logger.debug("Loading metadata for %s"%(name,))
	path = os.path.join(settings['sourceDir'], name)
	if not ('ignore_cache' in options and options['ignore_cache']):
		cached_metadata = load_cached_metadata(settings, name)
	if 'name' in cached_metadata:	# valid cached data
		if 'preferCachedData' in settings and \
		   settings['preferCachedData']:
			logger.debug("Preferring cached data for %s"%(name,))
			return cached_metadata
		else:
			logger.debug("Loaded cached data for %s"%(name,))
	new_metadata = {"name":name, "path":path}
	for parser_name in settings['parsers']:
		parser = load_parser(parser_name)
		if 'parser_options' in settings and \
		   parser_name in settings['parser_options']:
			parser_options = settings['parser_options'][parser_name]
		else:
			parser_options = {}
		try:
			if 'regex' in parser_options:
				regex = re.compile(parser_options['regex'])
				if not regex.search(new_metadata['path']):
					continue
			item_metadata = parser.get_metadata(dict(new_metadata), parser_options)
			if item_metadata == None:
				log_unknown_item(settings['cacheDir'], parser_name, name)
				continue
		except KeyboardInterrupt:
			raise
		except:
			log_crashed_parser(settings['cacheDir'], parser_name, name)
			continue
		deep_merge(new_metadata, item_metadata)
	
	metadata = cached_metadata
	metadata.update(new_metadata)
	save_cached_metadata(settings, metadata)
	return metadata

# Cache system
def get_cache_key(name):
	h = hashlib.new('md5')
	h.update(name.encode('utf-8'))
	return h.hexdigest()

def get_cache_path(settings, name):
	cache_key = get_cache_key(name)
	cache_dir = settings['cacheDir']
	cache_path = "%s/.cache-%s"%(cache_dir, cache_key)
	return cache_path

def load_cached_metadata(settings, name):
	""" Loads up any previously cached dat
	Returns {} if no data could be loaded
	"""
	cache_path = get_cache_path(settings, name)
	if 'parser_options' in settings:
		parser_options = json.dumps(settings['parser_options'])
	else:
		parser_options = None
	try:
		with open(cache_path) as reading:
			data = reading.read()
			parsed_data = json.loads(data)
			# check that th cache's parser_options are the same
			if 'parser_options' in parsed_data and \
			   parsed_data['parser_options'] != parser_options:
				return {}
			if 'parser_options' in parsed_data:
				del parsed_data['parser_options']
			return parsed_data
	except:
		if os.path.isfile(cache_path):
			msg = "Failed to open cache file for %s (%s): %s" % \
			      (name, cache_path)
			logger.warning(msg)
		return {}

def save_cached_metadata(settings, data):
	cache_path = get_cache_path(settings, data['name'])
	if 'parser_options' in settings:
		data['parser_options'] = settings['parser_options']
	try:
		with open(cache_path, 'w') as writing:
			writing.write(json.dumps(data))
	except:
		msg = "Failed to save cache file for %s (%s): %s" % \
		      (data['name'], cache_path, traceback.format_exc())
		logger.warning(msg)

# Actual organizing
def do_output(options, settings, metadata):
	for group in settings['output']:
		destdir = group['dest']
		if isinstance(group['groupBy'], str):
			groupsBy = [group['groupBy']]
		else:
			groupsBy = group['groupBy']
		for groupBy in groupsBy:
			if not groupBy in metadata:
				continue
			do_output_group(settings['name'], destdir, metadata, groupBy)

def do_output_group(setname, destdir, metadata, groupBy):
	logger.debug("Sorting %s by %s"%(metadata['name'],groupBy))
	value = metadata[groupBy]
	if isinstance(value,str):
		values = [value]
	else:
		values = value
	for value in sorted(set(values)):
		if value == None:
			continue
		value = value.replace('/','／')
		do_output_single(destdir, setname, metadata['path'], metadata['name'], value)

def do_output_single(destdir, setname, itempath, itemname, value):
	""" Adds an item from the set into the collection named value
	Adds FF8 from Albums into collection named Nobuo Uematsu
	"""
	logger.debug("Putting %s into %s"%(itemname,value))
	valueDir = os.path.join(destdir, value)
	if not os.path.isdir(valueDir):
		os.mkdir(valueDir)
	with open(os.path.join(destdir, '.toc-%s'%(setname,)), 'a') as toc:
		toc.write("%s\n"%(value,))
	destpath = os.path.join(valueDir, itemname)
	link = os.path.relpath(itempath, valueDir)
	if os.path.islink(destpath) and \
	   os.readlink(destpath) != link:
		os.unlink(destpath)
	if not os.path.islink(destpath):
		os.symlink(link, destpath)
	with open(os.path.join(valueDir, '.toc-%s'%(setname,)), 'a') as toc:
		toc.write("%s\n"%(itemname,))

# Preparation
def prepare_for_organization(settings):
	for parser_name in settings['parsers']:
		parser = load_parser(parser_name)
		if not parser:
			raise errors.MissingParser("Set %s can't load parser %s"%(settings['name'], parser_name))
	if not os.path.isdir(settings['sourceDir']):
		raise errors.MissingSourceDir("Set %s has an invalid sourceDir %s"%(settings['name'], settings['sourceDir']))
	if 'cacheDir' not in settings:
		settings['cacheDir'] = os.path.join(settings['sourceDir'], '.cache')
	prepare_cache_dir(settings['cacheDir'])

	if 'output' in settings:
		for output_dir in settings['output']:
			if not os.path.isdir(output_dir['dest']):
				raise errors.MissingDestDir("Set %s is missing an output directory %s"%(settings['name'], output_dir['dest']))

def prepare_cache_dir(cache_dir):
	join = os.path.join
	dirs = [cache_dir]
	for d in dirs:
		if not os.path.isdir(d):
			os.mkdir(d)

def generate_omitted_dirs(settings):
	dirs = []
	dirs.append(os.path.join(settings['cacheDir']))
	dirs.extend([o['dest'] for o in settings['output']])
	return dirs

# Progress tracking
def load_progress(settings):
	progress_filename = os.path.join(settings['cacheDir'], 'progress')
	if os.path.isfile(progress_filename):
		progress_file = open(progress_filename,'r')
		return [x.strip() for x in progress_file.readlines() if x.strip()!='']
	return []

def start_progress(settings):
	failed = os.path.join(settings['cacheDir'], 'failed.log')
	if os.path.isfile(failed):
		os.unlink(failed)
	unknown = os.path.join(settings['cacheDir'], 'unknown.log')
	if os.path.isfile(unknown):
		os.unlink(unknown)

def add_progress(settings, name):
	progress_filename = os.path.join(settings['cacheDir'], 'progress')
	with open(progress_filename,'a') as progress_file:
		progress_file.write("%s\n"%(name,))

def finish_progress(settings):
	if not ('noclean' in settings and settings['noclean']):
		cleanup_extra_output(settings)
	progress_filename = os.path.join(settings['cacheDir'], 'progress')
	if os.path.isfile(progress_filename):
		os.unlink(progress_filename)

# Finishing up and cleaning
def cleanup_extra_output(settings):
	logger.info("Cleaning up old files")
	for output in settings['output']:
		cleanup_extra_toc(settings, output['dest'], recurse_levels=1)

def safe_delete_dir(path):
	# Extra files that we are allowed to delete
	allowed_deletions_patterns = ['.toc', '.toc-*', '.toc.*']
	allowed_deletions = []
	for pattern in allowed_deletions_patterns:
		found_deletions = glob.glob(os.path.join(path, pattern))
		trimmed_deletions = [x[len(path)+1:] for x in found_deletions]
		allowed_deletions.extend(trimmed_deletions)
	if '.toc.extra' in allowed_deletions:
		allowed_deletions.remove('.toc.extra')

	# load up the list of extra things that we should not delete
	nameextra = os.path.join(path,'.toc.extra')
	extra_contents = []
	try:
		with open(nameextra) as extra:
			extra_contents = [x.strip() for x in extra.readlines()
			                  if x.strip()!='']
	except:
		pass

	# start unlinking things
	for name in os.listdir(path):
		if name in extra_contents:
			continue
		spath = os.path.join(path, name)
		try:
			if not os.path.islink(spath) and \
			   os.path.isdir(spath):
				safe_delete_dir(spath)
			if not os.path.islink(spath) and \
			   os.path.isfile(spath):
				if name in allowed_deletions:
					os.unlink(spath)
			if os.path.islink(spath):
				os.unlink(spath)
		except:
			raise
			msg = "An error happened while safely cleaning %s: %s" % \
			      (spath, traceback.format_exc())
			logger.warning(msg)

	if len(os.listdir(path)) == 0:
		os.rmdir(path)

def cleanup_extra_toc(settings, path, recurse_levels = 1):
	nametoc = os.path.join(path,'.toc-%s'%(settings['name'],))
	namedone = os.path.join(path,'.toc.done-%s'%(settings['name'],))
	nameold = os.path.join(path,'.toc.old-%s'%(settings['name'],))
	nameextra = os.path.join(path,'.toc.extra')
	if not os.path.isfile(nametoc):
		return

	# move around the old toc
	if os.path.isfile(nameold):
		os.unlink(nameold)
	if os.path.isfile(namedone):
		os.rename(namedone, nameold)

	# any other elements that are manually excepted
	extra_contents = []
	try:
		with open(nameextra, 'r') as extra:
			extra_contents = [x.strip() for x in extra.readlines()
			                  if x.strip()!='']
	except:
		pass

	# any other directories we need, and should not delete
	extra_paths = []
	extra_paths.append(settings['sourceDir'])
	extra_paths.append(settings['cacheDir'])
	extra_paths.extend([o['dest'] for o in settings['output']])

	# load the list of proper files in this dir
	proper_contents = []
	for alttoc in glob.glob(os.path.join(path, '.toc.done*')):
		with open(alttoc, 'r') as toc:
			proper_contents.extend([x.strip() for x in toc.readlines() if x.strip()!=''])
	with open(nametoc, 'r') as toc:
		proper_contents.extend([x.strip() for x in toc.readlines() if x.strip()!=''])

	# start deleting stuff
	for name in os.listdir(path):
		if name[:4] == '.toc':
			continue
		subpath = os.path.join(path,name)
		if subpath not in extra_paths and \
		   name not in proper_contents and \
		   name not in extra_contents:
			if not ('fakeclean' in settings and
				settings['fakeclean']):
				if not os.path.islink(subpath) and \
				   os.path.isdir(subpath):
					logger.debug("Removing extra dir %s"%(subpath,))
					safe_delete_dir(subpath)
				elif os.path.islink(subpath):
					logger.debug("Removing extra link %s"%(subpath,))
					os.unlink(subpath)
				else:
					logger.debug("Not removing extra file %s"%(subpath,))
			else:
				if not os.path.islink(subpath) and \
				   os.path.isdir(subpath):
					logger.debug("Would remove extra dir %s"%(subpath,))
				elif os.path.islink(subpath):
					logger.debug("Would remove extra file %s"%(subpath,))
				else:
					logger.debug("Would not remove extra file %s"%(subpath,))
		else:
			if os.path.isdir(subpath) and recurse_levels > 0:
				cleanup_extra_toc(settings, subpath, recurse_levels - 1)
			else:
				pass

	# declare this toc done
	os.rename(nametoc, namedone)

# Logging
def log_unknown_item(cache_dir, parser_name, item_name):
	logger.warning("%s couldn't locate %s"%(parser_name, item_name))
	with open(os.path.join(cache_dir, "unknown.log"), 'a') as log:
		log.write("%s couldn't locate %s\n"%(parser_name, item_name))

def log_crashed_parser(cache_dir, parser_name, item_name):
	message = "%s crashed while parsing %s:\n%s"%(parser_name, item_name, traceback.format_exc())
	logger.error(message)
	with open(os.path.join(cache_dir, "failed.log"), 'a') as log:
		log.write(message+"\n")
