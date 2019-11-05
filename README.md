# iLMS TA script

## Login

### Using username and password

```
from ilms import ILMS
ilms = ILMS.login('108062999', 'pa55w0rd', course=40596)
```

course is the courseID which appears on the URL

### Using an existing session

```
import requests
from ilms import ILMS
s = requests.Session()
s.cookies['PHPSESSID'] = 'qF7P5Zj80sONYH5KQmVwR1Hk8t'
```

You can get PHPSESSID from browser developer tools

As a security note, plain text `PHPSESSID`s are as bad as plain text passwords.

## Features

* Set homework score
* Send emails one by one
