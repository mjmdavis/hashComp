import hashlib
from bitarray import bitarray
from bitarray import bitdiff
import requests
import string
import collections
import itertools
import redis
import time
import sympy as sp
from sympy import S
from sympy import stats

def hashString(s):
    hs = hashlib.md5(s).digest()
    b = bitarray()
    b.frombytes(hs)
    return b

_targetHash = None
_targetString = 'novena'
def getTargetHash():
    global _targetHash
    global _targetString
    if None == _targetHash:
        _targetHash = hashString(_targetString)
    return _targetHash

def scoreString(s):
    return 128 - bitdiff(hashString(s), getTargetHash())

def getDifficulty():
    r = requests.get('http://novena-puzzle.crowdsupply.com/difficulty')
    d = r.json()['difficulty']
    return d

_binom128 = None
def getBinom128():
    global _binom128
    if None == _binom128:
        _binom128 = sp.stats.Binomial('X', 128,S.Half)
    return _binom128

def pOfFindingString(diff=getDifficulty(), tries=None):
    pWin = sp.stats.P(getBinom128()>=diff).evalf()
    if tries:
        pWin = 1- pow(1 - pOfFindingString().evalf(), tries)
    return pWin

#def timeToFindString(diff=getDifficulty(), triesPerSec=1.0):

def generateStringDict(length=1, keepScoresFrom=85):
    ddict = collections.defaultdict(set)
    for sTup in itertools.product(string.printable, repeat=length):
        s = ''.join(sTup)
        if scoreString(str(s)) >= keepScoresFrom:
            ddict[scoreString(str(s))].add(s)
    return ddict

def fgenerateStringDict(length=1):
    ddict = collections.defaultdict(set)
    for sTup in itertools.product(string.printable, repeat=length):
        s = ''.join(sTup)
        if scoreString(str(s)) > 80:
            ddict[scoreString(str(s))].add(s)
    return ddict

def submitString(string):
    data = {'username': 'pingbat', 'contents': string}
    headers = {'Content-type': 'application/json', 'Accept': 'text/plain'}
    r = requests.post(url, data=json.dumps(data), headers=headers)

_dbConnection = None
def getDB():
    global _dbConnection
    if _dbConnection == None:
        _dbConnection = redis.Redis()
    return _dbConnection

def saveString(string, score=None, foundby='unknown', foundtime=time.time()):
    if None==score:
        score = scoreString(string)
    pipe = getDB().pipeline()
    vals = {'score': score,
            'foundby': foundby,
            'foundtime': foundtime
            }
    pipe.hmset('string:%s' % string, vals)
    pipe.sadd('score:%i' % score, string)
    return pipe.execute()
