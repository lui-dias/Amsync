import sys
from sys import argv
from re import search
from subprocess import run
from colorama import Fore, init
from platform import system
from pathlib import Path
init()


def clear():
    a = 'cls' if system() == 'Windows' else 'clear'
    run(a, shell=True)

def exit(m):
    print(m)
    sys.exit(1)

def create(name):
    return {
        'Starting repository':                               'git init',
        'Adding files':                                      'git add .',
        'Committing repository':                             'git commit -m "Add in heroku"',
       f'Creating {Fore.CYAN}{name} {Fore.WHITE}on heroku': f'heroku create {name}',
        'Adding project on heroku':                          'git push heroku master',
        'Starting bot':                                      'heroku ps:scale worker=1'
    }

def update():
    return {
        'Adding files':               'git add .',
        'Committing repository':      'git commit -m "Update"',
        'Updating project on heroku': 'git push heroku master',
    }

def apps():
    return {
        '': 'heroku apps'
    }

def destroy(app):
    return {
        '': f'heroku destroy {app} -c {app}'
    }

def start():
    return {
        '': 'heroku ps:scale worker=1'
    }

def stop():
    return {
        '': 'heroku ps:stop worker'
    }

def restart():
    return {
        '': 'heroku ps:restart'
    }

def workers():
    return {
        '': 'heroku ps'
    }

def init():
    with open('Procfile', 'w') as f:
        f.write('worker: python bot.py')
    with open('runtime.txt', 'w') as f:
        f.write('python-3.8.9')
    with open('requirements.txt', 'w') as f:
        f.write('amsync')

    if not Path('.env').exists():
        with open('.env', 'w') as f:
            f.write('EMAIL=\nPASSWORD=')
    
    if not Path('bot.py').exists():
        with open('bot.py', 'w') as f:
            f.write(
"""
from amsync import Bot, Message

bot = Bot()

@bot.on()
async def ready():
    print('Ready')

@bot.add()
async def hello(m: Message):
    await bot.send(f'Hello {m.nickname}')

bot.run()

""".strip())

def run(cmds):
    for text, cmd in cmds.items():
        if text:
            print(text)
        tmp = run(cmd, capture_output=True, text=True, shell=True)
        if tmp.returncode:
            print(f'{Fore.RED}Error in: {Fore.RESET}{cmd}')
            if tmp.stderr:
                exit(tmp.stderr)
            else:
                exit(tmp.stdout)

    return tmp.stdout or tmp.stderr

def main():
    args = ' '.join(argv[1:])

    if args == 'init':
        init()
        print('Done')

    if args == 'start':
        print(run(start()))

    if args == 'stop':
        print(run(stop()))

    if args == 'restart':
        print(run(restart()))

    if args == 'workers':
        print(run(workers()))

    if 'create' in args:
        try:
            app = args.split()[1]
            search(r'^([a-z]|[0-9]|-){3,}$', app).group(0)
            run(create(app))
        except IndexError:
            exit('No project name')
        except AttributeError:
            exit('Invalid name')

    elif args == 'apps':
        print(run(apps()))
            

    elif 'destroy' in args:
        try:
            app = args.split()[1]
            print(run(destroy(app)))
        except IndexError:
            app = run(apps()).split('\n')[1:-2]
            if not app or not app[0]:
                exit('No project found')
            while True:    
                clear()
                for i, e in enumerate(app):
                    print(f'{Fore.CYAN}{i}. {Fore.WHITE}{e}')

                try:
                    n = int(input('\nNumber: '))
                    if n < 0 or n >= len(app):
                        continue
                except ValueError:
                    continue
                break

            clear()
            print(f'Destroing {Fore.CYAN}{app[n]}{Fore.WHITE}')
            run(destroy(app[n]))
