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
    def __init__(self, session, *, course, homework=None):
        self.sess = session
        self.course = course
        self.homework = homework
        self.show_course_info()
        self.students = self.fetch_students()
        self.groups = None

    @classmethod
    def login(cls, account, password, *, course, homework=None):
        """
        create an ILMS object by account and password.

        course: the courseID at the URL.
        """
        sess = requests.Session()
        resp = sess.get(
            'https://lms.nthu.edu.tw/sys/lib/ajax/login_submit.php',
            params={
                'account': account,
                'password': password,
            },
        )
        j = resp.json()
        if j['ret']['status'] != "true":
            raise LoginFailed(resp.json())
        return cls(sess, course=course, homework=homework)

    def show_course_info(self):
        resp = self.sess.get(f'http://lms.nthu.edu.tw/course/{self.course}')
        html = lxml.html.fromstring(resp.content)
        course_name, = html.xpath(
            '//select[@onchange="changeCourse(this)"]/'
            'option[@selected]/text()')
        print('Course:', course_name)

        if self.homework is not None:
            resp = self.sess.get(
                'http://lms.nthu.edu.tw/course.php',
                params={
                    'courseID': self.course,
                    'f': 'hw',
                    'hw': self.homework
                }
            )
            html = lxml.html.fromstring(resp.content)
            homework_name, = html.xpath('//span[@class="curr"]/text()')
            print('Homework:', homework_name)

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

    def fetch_groups(self, force=False):
        if (self.groups != None) and (not force):
            return self.groups
        groups = []
        resp = self.sess.get(
            'http://lms.nthu.edu.tw/course.php',
            params={'f': 'grouplist', 'courseID': self.course})
        html = lxml.html.fromstring(resp.content)
        table, = html.xpath('//*[@id="t1"]')
        trs = table.xpath('tr[@class!="header"]')
        for tr in trs:
            memberurl, = tr.xpath('td[6]/span/a[2]/@href')
            member_resp = self.sess.get('http://lms.nthu.edu.tw' + memberurl)
            member_html = lxml.html.fromstring(member_resp.content)
            member_table, = member_html.xpath('//*[@id="t1"]')
            member_trs = member_table.xpath('tr[@class!="header"]')
            members = []
            for member_tr in member_trs:
                members.append(member_tr.xpath('td[2]/div')[0].text)
            qs = urllib.parse.parse_qs(memberurl)
            groups.append({'teamID': qs['teamID'][0], 'members': members})
        print(len(groups), 'groups')
        self.groups = groups
        return groups

    def set_team_scores(self, team_number, members_scores):
        """
            team_number: team number, starting at 1
            member_scores: dict of student id => scores,
                for example: {'108080111': 99, '108090222': 88}
        """
        if self.groups is None:
            raise AddScoreFailed("fetch_groups() before set_team_scores()")
        teamID = self.groups[team_number-1]['teamID']
        scores = []
        for mem in members_scores:
            if mem in self.students:
                scores.append(self.students[mem] + ':' + str(members_scores[mem]))
        scores_str = ','.join(scores)
        hw_list_resp = self.sess.get(
            'http://lms.nthu.edu.tw/course.php',
            params={'f': 'hw_doclist', 'courseID': self.course, 'hw': self.homework})
        hw_list_html = lxml.html.fromstring(hw_list_resp.content)
        table, = hw_list_html.xpath('//*[@id="t1"]')
        trs = table.xpath('tr[@class!="header"]')
        submitted = False
        for tr in trs:
            td_a = tr.xpath('td/a')[0]
            if teamID in td_a.attrib['href']:
                if td_a.text == '修改':
                    submitted = True
                break
        resp = self.sess.post(
            'http://lms.nthu.edu.tw/course/score/http_update_group_score.php',
            headers={'Referer': 'http://lms.nthu.edu.tw/course/hw_group_score.php'},
            data={
                'paper': 0,
                'courseID': self.course,
                'folderID': self.homework,
                'teamID': teamID,
                '_public': 0,
                'status': 1,
                'scoreNote': ' ',
                'updateNewScore': (scores_str if submitted else 'NULL'),
                'insertNewScore': ('NULL' if submitted else scores_str)
            }
        )
        return resp

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
