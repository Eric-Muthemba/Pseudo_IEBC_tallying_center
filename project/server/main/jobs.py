# project/server/main/tasks.py
from rq.decorators import job
from rq import get_current_job
from server.main.rq_helpers import redis_connection
import os

from server.models import Tallying
import requests
import glob
import zipfile
import boto3

from flask import current_app


class aws_textract(object):
    def job(self,client, object_name,id):
        response = client.detect_document_text( Document={'Bytes': object_name})
        results = []
        polling_station ="object_name"
        for idx,item in enumerate(response["Blocks"]):
            try:
                if "POLLING STATION" in item["Text"].upper() and "NAME" in item["Text"].upper():
                    polling_station = (" ".join(item["Text"].upper().split("STATION")[1:]))
                elif item["BlockType"] == "LINE" and  "ODINGA" in item["Text"].upper():
                    for i in range(0,10):
                        results.append(response["Blocks"][idx+i]["Text"])
            except:
                pass

        response = {}
        for candidate, votes in zip(results[0::2][0:4],
                                    [result for result in results if result.isnumeric() and len(result) != 1][0:4]):
            response[candidate[2:]] = int(votes)



        return {"polling_station":polling_station,"results":response}

class IEBC_Tallying_Center(object):
  def __init__(self):

    self.base_url = "https://forms.iebc.or.ke/form/exportable_zip/"
    self.headers = {
                    'authority': 'forms.iebc.or.ke',
                    'accept': 'application/json, text/plain, */*',
                    'accept-language': 'en-US,en;q=0.9',
                    'cache-control': 'no-cache',
                    'cookie': '_ga=GA1.3.80109923.1660144513; _gid=GA1.3.1408002871.1660248408; _gat=1',
                    'pragma': 'no-cache',
                    'referer': 'https://forms.iebc.or.ke/',
                    'sec-ch-ua': '"Chromium";v="104", " Not A;Brand";v="99", "Google Chrome";v="104"',
                    'sec-ch-ua-mobile': '?0',
                    'sec-ch-ua-platform': '"macOS"',
                    'sec-fetch-dest': 'empty',
                    'sec-fetch-mode': 'cors',
                    'sec-fetch-site': 'same-origin',
                    'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/104.0.0.0 Safari/537.36'
                  }

    self.aws = aws_textract()
    self.client = boto3.client(
        'textract',
        region_name='us-east-2',
        aws_access_key_id=os.getenv("aws_access_key_id"),
        aws_secret_access_key=os.getenv("aws_secret_access_key")
    )


  def store_to_db(self,data):
      from server import db, create_app
      from server.config import Config
      app = create_app()
      app.config.from_object(Config)
      app.app_context().push()

      raila,ruto,wajackoyah,mwaure = [None,None,None,None]

      for key in data["results"].keys():
          if "RAILA" in key:
              raila = data["results"][key]
          elif "RUTO" in key:
              ruto = data["results"][key]
          elif "GEORGE" in key:
              wajackoyah = data["results"][key]
          elif "DAVID" in key:
              mwaure = data["results"][key]

      results = Tallying(polling_station=data['polling_station'],
                         raila=raila,
                         wajackoyah=wajackoyah,
                         ruto=ruto,
                         mwaure=mwaure)

      db.session.add(results)
      db.session.commit()

  def download_all_results(self,url_path,self_job):
      response = requests.request(method="GET",
                                  url=self.base_url + url_path,
                                  headers=self.headers,
                                  allow_redirects=True,
                                  stream=True)

      total_length = response.headers.get('content-length')

      with open("/app/data/results/"+url_path, "wb") as f:
          if total_length is None:  # no content length header
              f.write(response.content)
          else:
              dl = 0
              total_length = int(total_length)
              for idx,data in enumerate(response.iter_content(chunk_size=4096)):
                  dl += len(data)
                  f.write(data)
                  done = int(100 * dl / total_length)
                  self_job.meta['progress'] = {
                      'num_iterations': total_length,
                      'iteration': dl ,
                      'percent': done
                  }
                  self_job.save_meta()

      self.extract_zips("/app/data/results/"+url_path)
      if os.path.exists("/app/data/results/"+url_path):
          os.remove("/app/data/results/"+url_path)

      return {"url":self.base_url + url_path,"status":"sucessfully downloaded"}

  def fetch_all_results(self,self_job):
    results = requests.request(method="GET",
                               url = self.base_url+"forms.json?r=1632614.6622551896",
                               headers=self.headers).json()

    return(results)

  def extract_zips(self,_file):
        try:
            with zipfile.ZipFile(_file, 'r') as zip_ref:
                zip_ref.extractall("/app/data/extracted_results_pdfs")
        except:
            print(_file)

  def extract_tables_using_aws_textract(self,self_job):
    form_34As_images = glob.glob("/app/data/extracted_results_pdfs/*")
    response = {}
    form_34As_images = [form_34As_images[0]]

    for idx , form_34As_image in enumerate(form_34As_images):
        with open(form_34As_image, 'rb') as document:
            pdf = bytearray(document.read())
        data =  self.aws.job(self.client,pdf,form_34As_image)
        response[data['polling_station']] = data["results"]

        self.store_to_db(data)

        self_job.meta['progress'] = {
            'num_iterations': len(form_34As_images),
            'iteration': idx+1,
            'percent': (idx+1 / len(form_34As_images) )* 100
        }
        self_job.save_meta()

        print(self_job.meta)
        print("_________________________________________")


    return response

iebc_tallying_center = IEBC_Tallying_Center()


@job('default', connection=redis_connection, timeout=7*24*60*60, result_ttl=7*24*60*60)
def extract_tables_using_aws_textract():
    self_job = get_current_job()
    response = iebc_tallying_center.extract_tables_using_aws_textract(self_job)
    return response

@job('default', connection=redis_connection, timeout=7*24*60*60, result_ttl=7*24*60*60)
def download_zip_file(url_path):
    self_job = get_current_job()
    response = iebc_tallying_center.download_all_results(url_path,self_job)
    return response

def fetch_from_iebc_portal():
    self_job = get_current_job()
    response = iebc_tallying_center.fetch_all_results(self_job)
    for idx, constituency in enumerate(response["34"]):
        download_zip_file.delay(constituency["file"])
    return response


