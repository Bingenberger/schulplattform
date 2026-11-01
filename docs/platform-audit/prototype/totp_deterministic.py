#!/usr/bin/env python3
"""Freeze whole synthetic replay test within one TOTP step; no source mutation."""
import os,sys,time,unittest
from unittest import mock
sys.path.insert(0,sys.argv[1]);os.environ['SL_OFFICE_ENV']='testing'
suite=unittest.defaultTestLoader.loadTestsFromName('tests.test_two_factor.LoginFlowTests.test_the_same_code_cannot_be_used_for_a_second_login')
fixed=int(time.time()//30)*30+5
with mock.patch('time.time',return_value=fixed):result=unittest.TextTestRunner(verbosity=2).run(suite)
raise SystemExit(not result.wasSuccessful())
