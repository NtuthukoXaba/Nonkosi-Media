from flask import Flask, render_template

app = Flask(__name__)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/admin')
def admin_home():
    return render_template('admin_home.html')

@app.route('/journalist')
def journalist_home():
    return render_template('journalist_home.html')

@app.route('/login')
def login():
    return render_template('Login.html')


if __name__ == '__main__':
    app.run(debug=True)
