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
import json

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

_dbConnection = None
def getDB():
    global _dbConnection
    if _dbConnection == None:
        _dbConnection = redis.Redis()
    return _dbConnection

def scoreString(s):
    return scoreHash(hashString(s))

def scoreHash(h):
    return 128 - bitdiff(h, getTargetHash())

def getDifficulty():
    r = requests.get('http://novena-puzzle.crowdsupply.com/difficulty')
    d = r.json()['difficulty']
    db = getDB()
    db.rpush('difficultyTime', '%i:%s'%(d, str(time.time())))
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

def generateStringDict(length=1, keepScoresFrom=86, sendToDB=True):
    ddict = collections.defaultdict(set)
    for sTup in itertools.product(string.printable, repeat=length):
        s = ''.join(sTup)
        if scoreString(str(s)) >= keepScoresFrom:
            ddict[scoreString(str(s))].add(s)
            if sendToDB:
                saveString(s)
    return ddict

def hexHash(binHash):
    return "".join("{:02x}".format(ord(c)) for c in binHash.tobytes())

def fgenerateStrings(length=1, keepScoresFrom=90):
    for sTup in itertools.product(string.printable, repeat=length):
        s = ''.join(sTup)
        if scoreString(str(s)) >= keepScoresFrom:
            saveString(s)

def submitString(string):
    data = {'username': 'pingbat', 'contents': string}
    headers = {'Content-type': 'application/json', 'Accept': 'text/plain'}
    r = requests.post('http://novena-puzzle.crowdsupply.com/submit', data=json.dumps(data))
    resp = json.loads(r.text)
    if resp['status'] == 'success':
        getDB().sadd('sumbittedStrings', string)
        getDB().rpush('successfulAttempts', str(resp))
    else:
        if resp['reason'] == u'already submitted':
            getDB().sadd('sumbittedStrings', string)
        getDB().rpush('failedAttempts', str(resp))
    return resp

def watchdog():
    r = getDB()
    while(True):
        diff = getDifficulty()
        knownS = list(sorted(r.keys('stringScore:*'), cmp=lambda x,y: cmp(int(x.split(':')[1]),int(y.split(':')[1]))))
        goodS = filter(lambda x: int(x.split(':')[1])>=diff, knownS)
        status='success'
        try:
            for scoreS in goodS:
                cands = r.sdiff(scoreS, 'sumbittedStrings')
                for cand in cands:
                    print 'submitting string: %s' % cand
                    resp = submitString(cand)
                    assert resp['status']=='success'
        except AssertionError:
            print 'crap, assertion error'
        time.sleep(30)



def saveHash(md5Hash, string=None, score=None, pipe=None):
    _pipe = pipe if pipe else getDB().pipeline()
    if not score:
        score = scoreHash(md5hash)
    stringHash = md5Hash.tobytes()
    vals = {'string': string,
            'score': score,
            }
    _pipe.hmset('hash:%s' % stringHash, vals)
    _pipe.sadd('hashScore:%i' % score, stringHash)
    if not pipe:
        return _pipe.execute()

def saveString(string, score=None, foundby='unknown', foundtime=time.time(), pipe=None):
    _pipe = pipe if pipe else getDB().pipeline()
    if not score:
        score = scoreString(string)
    vals = {'score': score,
            'foundBy': foundby,
            }
    _pipe.hmset('string:%s' % string, vals)
    _pipe.hsetnx('string:%s' % string, 'foundTime', foundtime)
    _pipe.sadd('stringScore:%i' % score, string)
    saveHash(hashString(string), string=string, score=score, pipe=pipe)
    if not pipe:
        return _pipe.execute()

