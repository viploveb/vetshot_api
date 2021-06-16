from flask import Flask, render_template, request, redirect, jsonify
from werkzeug.utils import secure_filename
import os
from uploadtos3 import upload_to_s3
import datetime
from flask_cors import CORS, cross_origin
from textract_filter import ex
from textract_output import textract_output

UPLOAD_FOLDER = "uploads"
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

app = Flask(__name__)
cors = CORS(app)

app.secret_key = "\xda9\x91\xe7q\x07h \x0b\xe0\x06P\xbf;}G"
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['CORS_HEADERS'] = 'Content-Type'


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@cross_origin()
@app.route('/shotvet/ocr', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        if 'file' not in request.files:
            return "no file part"
            return redirect(request.url)
        file = request.files['file']
        if file.filename == '':
            return "No file selected! Please select a file."
            return redirect(request.url)
        if allowed_file(file.filename) is False:
            return "Invalid file type! Allowed file types are png, jpg, jpeg"
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            location_id = request.form.get("location_id")
            location_id = {"location_id" : location_id}
            # Image upload to s3
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename)) 
            upload_to_s3("./uploads/{}".format(filename),filename)
            
            # Rekognition output 
            output = textract_output(filename)

            # Filter output
            result, result_su, ret = ex(output)
            #result = ex(output)

            # image deletion
            os.remove(os.path.join(app.config['UPLOAD_FOLDER'], filename))

            # update output_logs, it contains result, location id, timestamp
            ct = datetime.datetime.now()
            log_file = open("output_logs.txt", "a")
            log_file.write("\n"+str(ct)+"\n"+str(location_id)+"\n"+result+"\n"+ret+"\n"+filename+"\n"+"--------------------------------------------" )
            log_file.close()
            
            #return location_id + "<br>" +  result
            return jsonify(location_id, ret)
    return render_template("index.html")

if __name__ == "__main__":
    app.run(debug=True)