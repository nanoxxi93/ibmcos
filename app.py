from flask import Flask, jsonify, request, url_for, render_template
from flask import render_template, Blueprint, make_response
# import uvicorn
# from fastapi import FastAPI, File, Form, UploadFile
import logging
import datetime
import json
import ibm_boto3
from ibm_botocore.client import Config, ClientError
import urllib.parse

app = Flask(__name__)
# app = FastAPI()

class PrefixMiddleware(object):
#class for URL sorting 
    def __init__(self, app, prefix=''):
        self.app = app
        self.prefix = prefix

    def __call__(self, environ, start_response):
        #in this line I'm doing a replace of the word flaskredirect which is my app name in IIS to ensure proper URL redirect
        if environ['PATH_INFO'].lower().replace('/cos','').startswith(self.prefix):
            environ['PATH_INFO'] = environ['PATH_INFO'].lower().replace('/cos','')[len(self.prefix):]
            environ['SCRIPT_NAME'] = self.prefix
            return self.app(environ, start_response)
        else:
            start_response('404', [('Content-Type', 'text/plain')])            
            return ["This url does not belong to the app.".encode()]

# Make the WSGI interface available at the top level so wfastcgi can get it.
# wsgi_app = app.wsgi_app
app.wsgi_app = PrefixMiddleware(app.wsgi_app, prefix='/api')

log_filename = 'log.log'
log_miniumlevel = logging.DEBUG
log_format = '%(asctime)s %(levelname)s %(message)s'
log_dateformat = '%Y%m%d.%H%M%S'
logging.basicConfig(
    handlers=[logging.FileHandler(
        filename=log_filename,
        encoding='utf-8',
        mode='a+'
    )],
    level=log_miniumlevel,
    format=log_format,
    datefmt=log_dateformat)

# Create resource
def fn_cos_create_resource(endpoint, apikey, instanceid):
    return ibm_boto3.resource("s3",
        ibm_api_key_id=apikey,
        ibm_service_instance_id=instanceid,
        config=Config(signature_version="oauth"),
        endpoint_url=endpoint
    )

# Simple upload
def fn_cos_upload_file(cos, bucket_name, item_name, form_file):
    try:
        response = cos.Object(bucket_name, item_name).put(
            Body=form_file.read()
        )
        return response
    except ClientError as be:
        raise ValueError("CLIENT ERROR: {0}\n".format(be))
    except Exception as e:
        raise e

# Multipart upload
def fn_cos_multi_part_upload(cos, bucket_name, item_name, form_file):
    try:
        # set 1 MB chunks
        part_size = 1024 * 1024 * 1

        # set threadhold to 15 MB
        file_threshold = 1024 * 1024 * 15

        # set the transfer threshold and chunk size
        transfer_config = ibm_boto3.s3.transfer.TransferConfig(
            multipart_threshold=file_threshold,
            multipart_chunksize=part_size
        )

        # the upload_fileobj method will automatically execute a multi-part upload
        # in 5 MB chunks for all files over 15 MB
        response = cos.Object(bucket_name, item_name).upload_fileobj(
            Fileobj=form_file,
            Config=transfer_config
        )
        return response
    except ClientError as be:
        raise ValueError("CLIENT ERROR: {0}\n".format(be))
    except Exception as e:
        raise e

@app.route('/upload', methods=['POST'])
def cos_upload_controller():
    endpoint = request.endpoint
    try:
        if (request.method == 'POST'):
            if (len(request.files) != 0):
                endpoint = request.form.get('endpoint')
                apikey = request.form.get('apikey')
                instanceid = request.form.get('instanceid')
                cos = fn_cos_create_resource(endpoint, apikey, instanceid)
                bucket_name = request.form.get('bucket_name')
                formfile = request.files[''] # obtiene el archivo de formdata
                filename = formfile.filename.rsplit(".",1)[0] # nombre del archivo
                fileextension = formfile.filename.rsplit(".",1)[1] # extensión del archivo
                logging.debug('{} --> REQUEST: {} {}'.format(endpoint, bucket_name, formfile.filename))
                response = fn_cos_upload_file(cos, bucket_name, formfile.filename, formfile)
                if (response['ResponseMetadata']['HTTPStatusCode'] == 200):
                    result = ''.join((endpoint, bucket_name, '/', urllib.parse.quote(formfile.filename)))
                    return jsonify(result), 200
                else:
                    raise ValueError('An error ocurrer with the uploading')
            else:
                raise TypeError('Request does not contain a file')
        else:
            return jsonify('Method not allowed')
    except (AssertionError, KeyError, TypeError, ValueError) as e:
        logging.exception(e)
        return jsonify(str(e).split(") ")[-1]), 400
    except Exception as e:
        logging.exception(e)
        return jsonify('Please contact with support'), 400

@app.route('/values')
def values_controller():
    return 'Api is running'

if __name__ == '__main__':
    from waitress import serve
    serve(app, host='0.0.0.0', port=8083) # waitress-serve --port=8083 app:app
    # uvicorn.run(app, host='0.0.0.0', port=8083) # uvicorn app:app --port=8083 --reload
    # app.run(host='0.0.0.0') # flask run