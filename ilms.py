import requests
import lxml.html
import urllib.parse


class LoginFailed(Exception):
    pass


class AddScoreFailed(Exception):
    pass


def form_multipart(d):
    return {
        k: (None, str(v))
        for (k, v) in d.items()
    }


class ILMS:
    def __init__(self):
        print("!!! please init by calling init_by_cookies or init_by_login first !!!\n")

        
    def init_by_cookies(self, cookie_string, course, homework):
        '''
        * cookie_string (from curl parameters): 'PHPSESSID=asdfasfasdfasdfasdf; cookie_locale=zh-tw; cookie_account=108685206; cookie_passwd=asdfasdfasdfasdfasdfasdfasdfasdf; ctx=abasdfasdf+asdfasdfasfasdf'
        * course: course id on ilms
        * homework: i don't know
        '''
        self.sess = requests.Session()
        for cookie in cookie_string.split(";"):
            equalpos = cookie.find("=")
            key, val = cookie[:equalpos].strip(), cookie[equalpos+1:].strip()
            self.sess.cookies.set(name=key, value=val)
        self.course = course
        self.homework = homework
        self.students = self.fetch_students()

    def init_by_login(self, account, password, course, homework):
        self.sess = requests.Session()
        resp = self.sess.get(
            'https://lms.nthu.edu.tw/sys/lib/ajax/login_submit.php',
            params={
                'account': account,
                'password': password,
            },
        )
        j = resp.json()
        if j['ret']['status'] != "true":
            raise LoginFailed(resp.json())
        self.course = course
        self.homework = homework
        self.students = self.fetch_students()

    def fetch_students(self):
        students = {}
        resp = self.sess.get(
            'http://lms.nthu.edu.tw/course.php',
            params={'f': 'member', 'courseID': self.course})
        html = lxml.html.fromstring(resp.content)
        table, = html.xpath('//*[@id="t1"]')
        trs = table.xpath('tr[@class!="header"]')
        for tr in trs:
            user_id, = tr.xpath('td[1]/input[@class="cb"]/@value')
            student_id, = tr.xpath('td[2]/text()')
            students[student_id.strip()] = user_id
        print(len(students), 'students')
        return students

    def fetch_submissions(self):
        resp = self.sess.get(
            'http://lms.nthu.edu.tw/course.php',
            params={'courseID': self.course, 'f': 'hw_doclist', 'hw': self.homework})
        html = lxml.html.fromstring(resp.content)
        table, = html.xpath('//*[@id="t1"]')
        trs = table.xpath('tr[@class!="header"]')
        submissions = {}
        for tr in trs:
            student_id, = tr.xpath('td[3]/div/text()')
            surl, = tr.xpath('td[2]/div/a/@href')
            cid, = urllib.parse.parse_qs(urllib.parse.urlparse(surl).query)['cid']
            submissions[student_id] = cid
        return submissions

    def add_score_by_user_id(self, student, score, note):
        response = self.sess.post(
            'http://lms.nthu.edu.tw/course/hw_paper_score.php',
            files=form_multipart({
                'fmSubmit': 'yes',
                'hw': self.homework,
                'userID': student,
                'fmScore': score,
                'fmNote': note,
            }),
            headers={
                'Referer': 'http://lms.nthu.edu.tw/course/hw_paper_score.php'
            }
        )
        return response

    def set_score_by_submission_id(self, id, score, note):
        response = self.sess.post(
            'http://lms.nthu.edu.tw/course/hw_score.php',
            data={
                'id': id,
                'fmStatus': 1,
                'fmSubmit': 'yes',
                'fmScore': score,
                'fmScoreNote': note,
            },
            headers={
                'Referer': 'http://lms.nthu.edu.tw/course/hw_score.php'
            }
        )
        assert b"status:'true'" in response.content, response.content.decode('utf8')
        return response

    def set_score_by_student_id(self, stuid, score, note):
        stuid = str(stuid)
        submissions = self.fetch_submissions()
        if stuid in submissions:
            return self.set_score_by_submission_id(submissions[stuid], score, note)
        self.add_score_by_user_id(self.students[stuid], score, note)

    def send_mail_by_user_id(self, user_id, subject, body):
        response = self.sess.post(
            'http://lms.nthu.edu.tw/course/member/email.php',
            files=form_multipart({
                'fmSubmit': 'yes',
                'courseID': self.course,
                'asst': '',
                'all': 0,
                'ids': user_id,
                'fmSendtanda': '',
                'fmTitle': subject,
                'fmNote': body,
                'fmCCSelf': 1,
            }),
            headers={
                'Referer': 'http://lms.nthu.edu.tw/course/member/email.php'
            }
        )
        assert b"'\xe5\xaf\x84\xe4\xbf\xa1\xe6\x88\x90\xe5\x8a\x9f'" in response.content

    def send_mail_by_student_id(self, student_id, subject, body):
        self.send_mail_by_user_id(self.students[student_id], subject, body)
