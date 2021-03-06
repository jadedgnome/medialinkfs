# -*- coding: UTF-8 -*-
import os
import tempfile
import shutil
import unittest

import logging
logging.basicConfig(level=logging.DEBUG, filename='tests.log')

import medialinkfs
import medialinkfs.organize
import medialinkfs.parsers.dummy as dummy

base = os.path.dirname(__file__)

class TestDummy(unittest.TestCase):
	def setUp(self):
		logging.debug("Initializing unittest %s"%(self.id(),))
		dummy.data = {"test": {
		  "actors": ["Sir George"]
		}}
		self.tmpdir = tempfile.mkdtemp()
		self.settings = {
			"name": "test",
			"parsers": ["dummy"],
			"scanMode": "directories",
			"sourceDir": os.path.join(self.tmpdir, "All"),
			"cacheDir": os.path.join(self.tmpdir, ".cache"),
			"output": [{
				"dest": os.path.join(self.tmpdir, "Actors"),
				"groupBy": "actors"
			}]
		}
		os.mkdir(os.path.join(self.tmpdir, "All"))
		os.mkdir(os.path.join(self.tmpdir, "All", 'test'))
		os.mkdir(os.path.join(self.tmpdir, "Actors"))

	def tearDown(self):
		shutil.rmtree(self.tmpdir)

	def test_dummy(self):
		res = dummy.get_metadata({"path":"/test"})
		self.assertNotEqual(None, res)
		self.assertEqual(1, len(res['actors']))
		self.assertEqual("Sir George", res['actors'][0])

	def test_dummy_bad_results(self):
		# missing groupby key
		del dummy.data['test']['actors']
		medialinkfs.organize.organize_set({}, self.settings)

		# empty result, logs a message saying that it can't find it
		del dummy.data['test']
		medialinkfs.organize.organize_set({}, self.settings)

	def test_dummy_organize(self):
		# does it create the link
		medialinkfs.organize.organize_set({}, self.settings)
		self.assertTrue(os.path.isdir(os.path.join(self.tmpdir, "Actors", "Sir George")))
		self.assertTrue(os.path.islink(os.path.join(self.tmpdir, "Actors", "Sir George", "test")))
		self.assertFalse(os.path.islink(os.path.join(self.tmpdir, "Actors", "Sir George", "test2")))

		# does it rename the link if the data changes
		os.rmdir(os.path.join(self.tmpdir, "All", 'test'))
		os.mkdir(os.path.join(self.tmpdir, "All", 'test2'))
		dummy.data['test2'] = dummy.data['test']
		del(dummy.data['test'])
		shutil.rmtree(self.settings['cacheDir'])
		medialinkfs.organize.organize_set({}, self.settings)
		self.assertTrue(os.path.isdir(os.path.join(self.tmpdir, "Actors", "Sir George")))
		self.assertFalse(os.path.islink(os.path.join(self.tmpdir, "Actors", "Sir George", "test")))
		self.assertTrue(os.path.islink(os.path.join(self.tmpdir, "Actors", "Sir George", "test2")))

		# does it change the link if the metadata changes
		dummy.data['test2']['actors'][0] = 'Sir Phil'
		shutil.rmtree(self.settings['cacheDir'])
		medialinkfs.organize.organize_set({}, self.settings)
		self.assertFalse(os.path.isdir(os.path.join(self.tmpdir, "Actors", "Sir George")))
		self.assertTrue(os.path.isdir(os.path.join(self.tmpdir, "Actors", "Sir Phil")))
		self.assertTrue(os.path.islink(os.path.join(self.tmpdir, "Actors", "Sir Phil", "test2")))

		# does it delete the directory with extra .toc files in it
		dummy.data['test2']['actors'][0] = 'Sir Lexus'
		lexus = os.path.join(self.tmpdir, "Actors", "Sir Lexus")
		phil = os.path.join(self.tmpdir, "Actors", "Sir Phil")
		open(os.path.join(phil, ".toc"),'w').close()
		open(os.path.join(phil, ".toc-TV"),'w').close()
		open(os.path.join(phil, ".toc.old-TV"),'w').close()
		medialinkfs.organize.organize_set({}, self.settings)
		self.assertTrue(os.path.isdir(os.path.join(lexus)))
		self.assertFalse(os.path.islink(os.path.join(phil, "test2")))
		self.assertFalse(os.path.isfile(os.path.join(phil, ".toc")))
		self.assertFalse(os.path.isfile(os.path.join(phil, ".toc-TV")))
		self.assertFalse(os.path.isfile(os.path.join(phil, ".toc.old-TV")))
		self.assertFalse(os.path.isdir(os.path.join(phil)))

	def test_dummy_cache(self):
		# does it create the link
		medialinkfs.organize.organize_set({}, self.settings)
		self.assertTrue(os.path.isdir(os.path.join(self.tmpdir, "Actors", "Sir George")))
		self.assertTrue(os.path.islink(os.path.join(self.tmpdir, "Actors", "Sir George", "test")))

		# delete the actors field and see if it uses cache
		del dummy.data['test']['actors']
		medialinkfs.organize.organize_set({}, self.settings)
		self.assertTrue(os.path.isdir(os.path.join(self.tmpdir, "Actors", "Sir George")))

		# now prefer the cache, even if the data has changed
		dummy.data['test']['actors'] = ['Sir Phil']
		self.settings['preferCachedData'] = True
		medialinkfs.organize.organize_set({}, self.settings)
		self.assertTrue(os.path.islink(os.path.join(self.tmpdir, "Actors", "Sir George", "test")))
		self.assertFalse(os.path.isdir(os.path.join(self.tmpdir, "Actors", "Sir Phil")))
		self.assertFalse(os.path.islink(os.path.join(self.tmpdir, "Actors", "Sir Phil", "test")))

		# now clear the cache and make sure it updates
		shutil.rmtree(self.settings['cacheDir'])
		medialinkfs.organize.organize_set({}, self.settings)
		self.assertFalse(os.path.islink(os.path.join(self.tmpdir, "Actors", "Sir George", "test")))
		self.assertTrue(os.path.isdir(os.path.join(self.tmpdir, "Actors", "Sir Phil")))
		self.assertTrue(os.path.islink(os.path.join(self.tmpdir, "Actors", "Sir Phil", "test")))

	def test_dummy_nocachedir(self):
		# does it create the link
		self.assertFalse(os.path.isdir(os.path.join(self.tmpdir, "All", ".cache")))
		del self.settings['cacheDir']
		medialinkfs.organize.organize_set({}, self.settings)
		self.assertTrue(os.path.isdir(os.path.join(self.tmpdir, "All", ".cache")))
		self.assertTrue(os.path.isdir(os.path.join(self.tmpdir, "Actors", "Sir George")))
		self.assertTrue(os.path.islink(os.path.join(self.tmpdir, "Actors", "Sir George", "test")))

	def test_dummy_noclean(self):
		# does it create the link
		medialinkfs.organize.organize_set({}, self.settings)
		self.assertTrue(os.path.isdir(os.path.join(self.tmpdir, "Actors", "Sir George")))
		self.assertTrue(os.path.islink(os.path.join(self.tmpdir, "Actors", "Sir George", "test")))

		# Add the setting, leaving it false
		self.settings['fakeclean'] = False
		dummy.data['test']['actors'] = ['Sir Phil']
		shutil.rmtree(self.settings['cacheDir'])
		medialinkfs.organize.organize_set({}, self.settings)
		self.assertFalse(os.path.islink(os.path.join(self.tmpdir, "Actors", "Sir George", "test")))
		self.assertFalse(os.path.isdir(os.path.join(self.tmpdir, "Actors", "Sir George")))
		self.assertTrue(os.path.isdir(os.path.join(self.tmpdir, "Actors", "Sir Phil")))
		self.assertTrue(os.path.islink(os.path.join(self.tmpdir, "Actors", "Sir Phil", "test")))

		# Set the setting to true
		self.settings['fakeclean'] = True
		dummy.data['test']['actors'] = []
		shutil.rmtree(self.settings['cacheDir'])
		medialinkfs.organize.organize_set({}, self.settings)
		self.assertFalse(os.path.islink(os.path.join(self.tmpdir, "Actors", "Sir George", "test")))
		self.assertFalse(os.path.isdir(os.path.join(self.tmpdir, "Actors", "Sir George")))
		self.assertTrue(os.path.isdir(os.path.join(self.tmpdir, "Actors", "Sir Phil")))
		self.assertTrue(os.path.islink(os.path.join(self.tmpdir, "Actors", "Sir Phil", "test")))

		# set the quiet noclean setting, but to false
		del self.settings['fakeclean']
		self.settings['noclean'] = False
		dummy.data['test']['actors'] = ['Sir Harry']
		shutil.rmtree(self.settings['cacheDir'])
		medialinkfs.organize.organize_set({}, self.settings)
		self.assertFalse(os.path.islink(os.path.join(self.tmpdir, "Actors", "Sir Phil", "test")))
		self.assertFalse(os.path.isdir(os.path.join(self.tmpdir, "Actors", "Sir Phil")))
		self.assertTrue(os.path.isdir(os.path.join(self.tmpdir, "Actors", "Sir Harry")))
		self.assertTrue(os.path.islink(os.path.join(self.tmpdir, "Actors", "Sir Harry", "test")))

		# set the quiet noclean setting to true
		self.settings['noclean'] = True
		dummy.data['test']['actors'] = []
		shutil.rmtree(self.settings['cacheDir'])
		medialinkfs.organize.organize_set({}, self.settings)
		self.assertFalse(os.path.islink(os.path.join(self.tmpdir, "Actors", "Sir Phil", "test")))
		self.assertFalse(os.path.isdir(os.path.join(self.tmpdir, "Actors", "Sir Phil")))
		self.assertTrue(os.path.isdir(os.path.join(self.tmpdir, "Actors", "Sir Harry")))
		self.assertTrue(os.path.islink(os.path.join(self.tmpdir, "Actors", "Sir Harry", "test")))

	def test_dummy_deepmerge(self):
		# does it create the link
		os.rmdir(os.path.join(self.settings['sourceDir'], 'test'))
		os.mkdir(os.path.join(self.settings['sourceDir'], 'Dynomutt Dog Wonder'))
		dummy.data['Dynomutt Dog Wonder'] = {}
		dummy.data['Dynomutt Dog Wonder']['actors'] = ['Sir George']
		medialinkfs.organize.organize_set({}, self.settings)
		self.assertTrue(os.path.isdir(os.path.join(self.tmpdir, "Actors", "Sir George")))
		self.assertTrue(os.path.islink(os.path.join(self.tmpdir, "Actors", "Sir George", "Dynomutt Dog Wonder")))

		# Now, change the dummy data from Sir George to Sir Phil
		# Then, add in another parser
		# It should ignore the cached data about Sir George because the new parser data
		# However, it should merge the two actors sections
		dummy.data['Dynomutt Dog Wonder']['actors'][0] = 'Sir Phil'
		self.settings['parsers'].append('omdbapi')
		medialinkfs.organize.organize_set({}, self.settings)
		self.assertFalse(os.path.isdir(os.path.join(self.tmpdir, "Actors", "Sir George")))
		self.assertTrue(os.path.isdir(os.path.join(self.tmpdir, "Actors", "Sir Phil")))
		self.assertTrue(os.path.isdir(os.path.join(self.tmpdir, "Actors", "Frank Welker")))

		# Try it the other way
		shutil.rmtree(self.settings['cacheDir'])
		self.settings['parsers'] = ['omdbapi', 'dummy']
		medialinkfs.organize.organize_set({}, self.settings)
		self.assertFalse(os.path.isdir(os.path.join(self.tmpdir, "Actors", "Sir George")))
		self.assertTrue(os.path.isdir(os.path.join(self.tmpdir, "Actors", "Sir Phil")))
		self.assertTrue(os.path.isdir(os.path.join(self.tmpdir, "Actors", "Frank Welker")))

	def test_dummy_dontdelete_extra(self):
		# does it create the link
		medialinkfs.organize.organize_set({}, self.settings)
		self.assertTrue(os.path.isdir(os.path.join(self.tmpdir, "Actors", "Sir George")))
		self.assertTrue(os.path.islink(os.path.join(self.tmpdir, "Actors", "Sir George", "test")))

		# create the extra bits
		george = os.path.join(self.tmpdir, 'Actors', 'Sir George')
		os.symlink(os.path.join(self.settings['sourceDir'], 'test'),\
		        os.path.join(george, 'test.extra'))
		with open(os.path.join(george, '.toc.extra'), 'w') as extra:
			extra.write("test.extra\n")

		# run the organization again, make sure it didn't delete our extra
		shutil.rmtree(self.settings['cacheDir'])
		dummy.data['test']['actors'][0] = 'Sir Phil'
		medialinkfs.organize.organize_set({}, self.settings)
		self.assertTrue(os.path.isfile(os.path.join(george, '.toc.extra')))
		self.assertTrue(os.path.isdir(os.path.join(self.tmpdir, "Actors", "Sir George")))
		self.assertFalse(os.path.islink(os.path.join(george, 'test')))
		self.assertTrue(os.path.islink(os.path.join(george, 'test.extra')))
		self.assertTrue(os.path.isdir(os.path.join(self.tmpdir, "Actors", "Sir Phil")))
		self.assertTrue(os.path.islink(os.path.join(self.tmpdir, "Actors", "Sir Phil", 'test')))

		# run it again, make sure that the extra file wasn't deleted
		medialinkfs.organize.organize_set({}, self.settings)
		self.assertTrue(os.path.isfile(os.path.join(george, '.toc.extra')))
		self.assertTrue(os.path.isdir(os.path.join(self.tmpdir, "Actors", "Sir George")))
		self.assertFalse(os.path.islink(os.path.join(george, 'test')))
		self.assertTrue(os.path.islink(os.path.join(george, 'test.extra')))
	def test_dummy_dontdelete_file(self):
		# does it create the link
		medialinkfs.organize.organize_set({}, self.settings)
		self.assertTrue(os.path.isdir(os.path.join(self.tmpdir, "Actors", "Sir George")))
		self.assertTrue(os.path.islink(os.path.join(self.tmpdir, "Actors", "Sir George", "test")))

		# make a real file
		with open(os.path.join(self.tmpdir, "Actors", "Sir George", "file"), 'w') as output:
			output.write("test file\n")

		# run the organization again, make sure it doesn't delete our file
		shutil.rmtree(self.settings['cacheDir'])
		dummy.data['test']['actors'][0] = 'Sir Phil'
		medialinkfs.organize.organize_set({}, self.settings)
		self.assertTrue(os.path.isdir(os.path.join(self.tmpdir, "Actors", "Sir George")))
		self.assertFalse(os.path.islink(os.path.join(self.tmpdir, "Actors", "Sir George", 'test')))
		self.assertTrue(os.path.isfile(os.path.join(self.tmpdir, "Actors", "Sir George", 'file')))
		self.assertTrue(os.path.isdir(os.path.join(self.tmpdir, "Actors", "Sir Phil")))
		self.assertTrue(os.path.islink(os.path.join(self.tmpdir, "Actors", "Sir Phil", 'test')))

	def test_dummy_multiset(self):
		# does it create the link
		medialinkfs.organize.organize_set({}, self.settings)
		self.assertTrue(os.path.isdir(os.path.join(self.tmpdir, "Actors", "Sir George")))
		self.assertTrue(os.path.islink(os.path.join(self.tmpdir, "Actors", "Sir George", "test")))

		newtmp = tempfile.mkdtemp()
		try:
			settings = {
				"name": "test2",
				"parsers": ["dummy"],
				"scanMode": "directories",
				"sourceDir": os.path.join(newtmp),
				"cacheDir": os.path.join(newtmp, ".cache"),
				"output": [{
					"dest": os.path.join(self.tmpdir, "Actors"),
					"groupBy": "actors"
				}]
			}
			os.mkdir(os.path.join(newtmp, 'test2'))
			dummy.data['test2'] = {'actors':['Sir George']}

			# try it
			medialinkfs.organize.organize_set({}, settings)
			self.assertTrue(os.path.isdir(os.path.join(self.tmpdir, "Actors", "Sir George")))
			self.assertTrue(os.path.islink(os.path.join(self.tmpdir, "Actors", "Sir George", "test")))
			self.assertTrue(os.path.islink(os.path.join(self.tmpdir, "Actors", "Sir George", "test2")))

			# try it with the old .toc.done file
			os.rename(os.path.join(self.tmpdir, "Actors", "Sir George", ".toc.done-test"), \
			          os.path.join(self.tmpdir, "Actors", "Sir George", ".toc.done"))
			shutil.rmtree(settings['cacheDir'])
			medialinkfs.organize.organize_set({}, settings)
			self.assertTrue(os.path.isdir(os.path.join(self.tmpdir, "Actors", "Sir George")))
			self.assertTrue(os.path.islink(os.path.join(self.tmpdir, "Actors", "Sir George", "test")))
			self.assertTrue(os.path.islink(os.path.join(self.tmpdir, "Actors", "Sir George", "test2")))

		finally:
			shutil.rmtree(newtmp)

	def test_dummy_parser_options(self):
		# does it create the link
		self.settings['parser_options'] = {
		  'dummy': {'should_exist':'True'},
		  'fake': {'should_exist':'False'}
		}
		self.settings['output'][0]['groupBy'] = 'should_exist'
		medialinkfs.organize.organize_set({}, self.settings)
		self.assertTrue(os.path.isdir(os.path.join(self.tmpdir, "Actors", "True")))
		self.assertTrue(os.path.islink(os.path.join(self.tmpdir, "Actors", "True", "test")))

	def test_dummy_regex(self):
		self.settings['regex'] = '^.*tst$'
		dummy.data['test.tst'] = dummy.data['test']
		os.mkdir(os.path.join(self.tmpdir, 'All', 'test.tst'))
		medialinkfs.organize.organize_set({}, self.settings)
		self.assertTrue(os.path.isdir(os.path.join(self.tmpdir, "Actors", "Sir George")))
		self.assertFalse(os.path.islink(os.path.join(self.tmpdir, "Actors", "Sir George", "test")))
		self.assertTrue(os.path.islink(os.path.join(self.tmpdir, "Actors", "Sir George", "test.tst")))
	def test_dummy_settings_regex(self):
		self.settings['parser_options'] = {'dummy':{'regex': '^.*tst$'}}
		dummy.data['test.tst'] = dummy.data['test']
		os.mkdir(os.path.join(self.tmpdir, 'All', 'test.tst'))
		medialinkfs.organize.organize_set({}, self.settings)
		self.assertTrue(os.path.isdir(os.path.join(self.tmpdir, "Actors", "Sir George")))
		self.assertFalse(os.path.islink(os.path.join(self.tmpdir, "Actors", "Sir George", "test")))
		self.assertTrue(os.path.islink(os.path.join(self.tmpdir, "Actors", "Sir George", "test.tst")))

	def test_dummy_multiple_groups(self):
		self.settings['output'][0]['groupBy'] = ['actors', 'extras']
		dummy.data['test2'] = {"extras": ["Sir George"]}
		os.mkdir(os.path.join(self.tmpdir, 'All', 'test2'))
		medialinkfs.organize.organize_set({}, self.settings)
		self.assertTrue(os.path.isdir(os.path.join(self.tmpdir, "Actors", "Sir George")))
		self.assertTrue(os.path.islink(os.path.join(self.tmpdir, "Actors", "Sir George", "test")))
		self.assertTrue(os.path.islink(os.path.join(self.tmpdir, "Actors", "Sir George", "test2")))
	def test_dummy_multiple_identical_groups(self):
		self.settings['output'][0]['groupBy'] = ['actors', 'extras']
		dummy.data['test'] = {"actors": ["Sir George"], "extras": ["Sir George"]}
		os.mkdir(os.path.join(self.tmpdir, 'All', 'test2'))
		medialinkfs.organize.organize_set({}, self.settings)
		self.assertTrue(os.path.isdir(os.path.join(self.tmpdir, "Actors", "Sir George")))
		self.assertTrue(os.path.islink(os.path.join(self.tmpdir, "Actors", "Sir George", "test")))
		self.assertFalse(os.path.islink(os.path.join(self.tmpdir, "Actors", "Sir George", "test2")))
