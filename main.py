#!/usr/bin/env python3

import flask
from flask import Flask, render_template, request, redirect, url_for, abort, Response
from werkzeug.security import generate_password_hash, check_password_hash
import sys
import json
import db
import data
import re
import mail
import session
import threading
import datetime

app = Flask("survey")
if not app.secret_key:
    app.secret_key = "cookie_secret"


sh_brushes = {
    "sh" : ("bash", "shBrushBash.js"),
    "adb" : ("ada", "shBrushAda.js"),
    "c" : ("c", "shBrushCpp.js"),
    "cs" : ("csharp", "shBrushCSharp.js"),
    "cpp" : ("cpp", "shBrushCpp.js"),
    "css" : ("css", "shBrushCss.js"),
    "js" : ("js", "shBrushJScript.js"),
    "java" : ("java", "shBrushJava.js"),
    "pl" : ("perl", "shBrushPerl.js"),
    "php" : ("php", "shBrushPhp.js"),
    "txt" : ("text", "shBrushPlain.js"),
    "ps" : ("powershell", "shBrushPowerShell.js"),
    "py" : ("python", "shBrushPython.js"),
    "rb" : ("ruby", "shBrushRuby.js"),
    "sql" : ("sql", "shBrushSql.js")
}


@app.route('/')
def index():
    return render_template('index.html')

# TODO: We want some other way of entering a survey...
@app.route('/list/')
def list():
    c = db.cursor()
    c.execute('SELECT id, name, file FROM surveys;')
    avail = []
    for r in c:
        d = data.get_json(r[2])
        avail.append((r[0], r[1], d['title']))
    db.commit()
    return render_template('list.html', avail=avail)

# TODO: Maybe we want a unique ID somewhere to prevent people from submitting fake responses...
@app.route('/enter/<name>', methods=['GET', 'POST'])
@app.route('/enter/<name>/<group>', methods=['GET', 'POST'])
def enter(name, group="-"):
    c = db.cursor()
    c.execute('SELECT id, file FROM surveys WHERE name == ?;', (name,))
    r = c.fetchone()
    db.commit()
    if r is None:
        return "Incorrect URL"

    survey_id = r[0]
    if str(survey_id) in flask.session:
        return redirect(url_for('page', token=flask.session[str(survey_id)]))

    d = data.get_json(r[1])
    if not d['open']:
        return ""

    if "next" in request.form:
        token = data.new_answers(group, survey_id, 1)
        flask.session[str(survey_id)] = token
        return redirect(url_for('page', token=token))

    return render_template('intro.html', data=d, id=survey_id)

def grade_answers(questions, answers):
    result = {}
    for k, v in questions.items():
        if k in answers and 'correct' in v:
            student_ans = answers[k]
            correct_ans = v['correct']
            result[k] = (student_ans, correct_ans)
    return result

def count_correct(answers):
    count = 0
    for k, v in answers.items():
        if compare_without_whitespace(v[0], v[1]):
            count += 1
    return count

def compare_without_whitespace(student_answer, correct_answer):
    return ''.join(student_answer.split()) == ''.join(correct_answer.split())

def format_answer(d, question, answer):
    q = d['questions'][question]
    type = q['type']
    if type == "value":
        type, val = answer.split(':', maxsplit=1)
        if type in d['value_types']:
            vt = d['value_types'][type]
            if 'format' in vt:
                return vt['format'].format(val)
            else:
                return vt['name'] + ": " + val
    elif type == "type":
        if answer in d['value_types']:
            return d['value_types'][answer]['name']
    elif type == "options":
        key = answer
        rest = ""
        if ':' in key:
            pos = key.index(':') + 1
            rest = " " + key[pos:]
            key = key[0:pos]

        try:
            id = q['keys'].index(key)
            return q['options'][id] + rest
        except ValueError:
            return answer
    return answer

def group_answers(d, answers):
    result = []
    for pageno, page in enumerate(d['pages']):
        cont = []
        for q in page['content']:
            if q in answers:
                ans = format_answer(d, q, answers[q][0])
                ref = format_answer(d, q, answers[q][1])
                ok = compare_without_whitespace(answers[q][0], answers[q][1])

                cont.append((d['questions'][q]['caption'], ans, ref, ok))
        if len(cont) > 0:
            info = {
                'page' : pageno + 1,
                'title' : page['title'],
                'content' : cont
            }

            if 'code' in page:
                code_file = page['code']
                code_ext = code_file.split('.')[-1]

                with open('./config/' + code_file, 'r', encoding='utf-8') as f:
                    info['code'] = f.read()

                info['code_brush'] = sh_brushes[code_ext][0]
                info['code_js'] = sh_brushes[code_ext][1]

            result.append(info)

    return result

def show_done(d, answer_id):
    score = None

    if 'results' in d:
        results = d['results']
        score = { 'type' : results['type'] }
        answers = grade_answers(d['questions'], data.answers_for(answer_id))
        score['text'] = results['text'].format(score=count_correct(answers), max=len(answers))

        if results['type'] == "timed":
            if 'date' in results:
                date = datetime.datetime.strptime(results['date'], '%Y-%m-%d')
            elif 'time' in results:
                date = datetime.datetime.strptime(results['time'], '%Y-%m-%d %H:%M')
            else:
                date = datetime.datetime.now()

            if date <= datetime.datetime.now():
                score['type'] = "summary"
            else:
                score['type'] = "score"

        if score['type'] == "score":
            pass
        elif score['type'] == "summary":
            groups = group_answers(d, answers)
            score['code_js'] = {x['code_js'] for x in groups if 'code_js' in x}
            score['pages'] = groups
            score['show_correct'] = results['show_correct']

    return render_template('done.html', data=d, score=score)

@app.route('/page/<token>', methods=['GET', 'POST'])
def page(token):
    global sh_brushes
    token_data = session.find(token)
    if token_data is None:
        return render_template('error.html', msg="No survey is active!")

    answer_id, page = token_data
    d = data.data_for_answer(answer_id)
    if d is None:
        return render_template('error.html', msg="Internal error!")

    page -= 1
    if page >= len(d['pages']):
        return show_done(d, answer_id)

    if page < 0:
        if 'next' in request.form:
            session.next_page(token)
            return redirect(url_for('page', token=token))
        return render_template('intro.html', data=d, id=token)

    page_data = d['pages'][page]
    if 'next' in request.form:
        try:
            answers = []
            for q in page_data['content']:
                q_data = d['questions'][q]
                if q_data['type'] == "plain-text":
                    continue

                if q not in request.form:
                    return render_template('error.html', msg="Missing answer!")
                answer = request.form[q].strip()
                if q_data['type'] == 'options' or q_data['type'] == 'options-list':
                    if 'keys' in q_data:
                        try:
                            index = int(answer)
                            answer = q_data['keys'][index]
                            if answer.endswith(':'):
                                answer += request.form[q + '_text_' + str(index)].strip()
                        except:
                            pass
                elif q_data['type'] == 'options-multi':
                    def translate(k):
                        if 'keys' in q_data:
                            try:
                                index = int(k)
                                ans = q_data['keys'][index]
                                if ans.endswith(':'):
                                    ans += request.form[q + '_text_' + str(index)].strip()
                                return ans
                            except:
                                return k
                        else:
                            return k

                    picked = [translate(k) for k in request.form.getlist(q)]
                    answer = ",".join(picked)
                elif q_data['type'] == 'value':
                    ans_type = d['value_types'][answer]
                    text = ""
                    if q + '_val' in request.form: # Disabled elements are not included.
                        text = request.form[q + '_val']
                    if 'remove' in ans_type and ans_type['remove'] is not None:
                        text = re.sub(ans_type['remove'], "", text)
                    answer = answer + ":" + text

                answers.append((q, answer))

            c = db.cursor()
            for key, ans in answers:
                c.execute('INSERT INTO questions(answer, question, reply) VALUES (?, ?, ?);', (answer_id, key, ans))
            db.commit()

            session.next_page(token)
            return redirect(url_for('page', token=token))
        except Exception as e:
            db.commit()
            raise e

    params = {
        'data' : d,
        'page' : page_data,
        'currpage' : page + 1,
        'numpages' : len(d['pages']),
        'questions' : [(i, d['questions'][i]) for i in page_data['content']],
        'value_types_json' : json.dumps(d['value_types']),
        'errors_json' : json.dumps(d['errors']),
        'value_types' : sorted(d['value_types'].items(), key=lambda k: k[1]['key'])
    }

    if 'code' in page_data:
        code_file = page_data['code']
        code_ext = code_file.split('.')[-1]

        with open('./config/' + code_file, 'r', encoding='utf-8') as f:
            params['code'] = f.read()
        params['code_js'] = sh_brushes[code_ext][1]
        params['code_brush'] = sh_brushes[code_ext][0]

    return render_template('page.html', **params)

def send_invitations(survey, group):
    c = db.cursor()
    c.execute('SELECT email FROM send_to WHERE survey == ? AND identifier == ?;', (survey, group))
    emails = [row[0] for row in c]
    c.execute('DELETE FROM send_to WHERE survey == ? AND identifier == ?;', (survey, group))
    db.commit()

    d = data.data_for_survey(survey)
    subject = d['email_subject']
    mails = []
    for addr in emails:
        token = data.new_answers(group, survey, 0)
        url = 'https://survey.fprg.se' + url_for('page', token=token)
        m = mail.Mail(addr, subject, 'invitation', url=url, data=d)
        mails.append(m)

    t = threading.Thread(target=mail.send_mails, args=(mails,), name='mailer')
    t.start()


@app.route('/manage', methods=['GET', 'POST'])
@app.route('/manage/', methods=['GET', 'POST'])
def manage():
    if 'survey' in request.form and 'group' in request.form:
        send_invitations(int(request.form['survey']), request.form['group'])
        return redirect(url_for('manage'))

    c = db.cursor()
    c.execute('SELECT DISTINCT send_to.survey, send_to.identifier, surveys.name FROM send_to INNER JOIN surveys ON send_to.survey == surveys.id')

    groups = {}
    ids = {}
    for row in c:
        survey_id = row[0]
        group_id = row[1]
        survey_name = row[2]

        ids[survey_name] = survey_id
        if survey_name in groups:
            groups[survey_name].append(group_id)
        else:
            groups[survey_name] = [group_id]

    db.commit()

    for k in groups:
        groups[k] = sorted(groups[k])

    return render_template('manage.html', groups=sorted(groups.items()), ids=ids)

if __name__ == "__main__":
    db.setup(app)

    commands = {
        "init_db" : lambda args: db.initialize(),
        "add" : data.add,
        "participants" : data.add_participants,
        "clean" : session.clean,
        "results" : data.results
    }

    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        args = sys.argv[2:]

        if not cmd in commands:
            print("Unknown command: {}".format(cmd))
            print("Try one of the following:")
            print(", ".join(commands.keys()))
            sys.exit(1)

        commands[cmd](args)
    else:
        app.run(debug=True)
        
