# 0.0.50

### **FEAT**
<br>

#### **[Bot.status] - Changes the status of the bot**
```py
@bot.on()
async def ready():
    await bot.status('on')
```

**NOTE:** The bot will take longer to start because it changes the status of all communities by default

<br>
<br>
<br>
<br>

# 0.0.47

### **FEAT**
<br>

#### **[Bot.add] - Added option for a command to be called by curator(curator), leader(leader) or both(any)**

```py
@bot.add(staff='curator'):
async def curator(m):
    await bot.send('A curator called me?')

@bot.add(staff='leader'):
async def leader(m):
    await bot.send('A leader called me?')

@bot.add(staff='any'):
async def any(m):
    await bot.send('A leader or curator called me?')
```
<br>
<br>

### **Check if the program is running with python >= 3.8**
\
If the version is < 3.8, it shows an error similar to this one
```
InvalidPythonVersion: Your python 3.7, use python >= 3.8
```

<br>
<br>

### **[MakeImage.text] - Best error message if the text font doesn`t exist**
```
FontNotFound: Font 'lato-light.ttf' was not found in the current folder
```