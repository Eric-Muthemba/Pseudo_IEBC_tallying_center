from server.main.rq_helpers import queue, get_all_jobs
from server.main import jobs
from flask import render_template, Blueprint, jsonify, request, send_file,current_app, redirect
from server.models import Tallying

main_blueprint = Blueprint("main", __name__, template_folder='templates')


# endpoint for monitoring all job status
@main_blueprint.route("/", methods=["GET"])
def home():
    return render_template('index.html')

# endpoint for monitoring all job status
@main_blueprint.route("/results", methods=["GET"])
def results():
    return render_template('results.html')


@main_blueprint.route("/repair_tab", methods=["GET"])
def repairtab():
    return render_template('repair.html')

@main_blueprint.route("/jobs", methods=["GET"])
def jobs_list():
    joblist = get_all_jobs()
    print(joblist)

    l = []
    # work on copy of joblist
    for job in list(joblist):
        l.append({
            'id': job.get_id(),
            'state': job.get_status(),
            'progress': job.meta.get('progress'),
            'result': job.result
            })

    return render_template('joblist.html', joblist=l)

@main_blueprint.route("/image_view/<image_name>", methods=["GET"])
def image_view(image_name):
    return send_file("../../data/extracted_results_pdfs/"+image_name)


# endpoint for adding job
@main_blueprint.route("/api/start_data_fetch_from_iebc_portal", methods=["GET"])
def run_wait_job_get():
    jobs.fetch_from_iebc_portal()
    return redirect('/')

# endpoint for adding job
@main_blueprint.route("/api/extract_data", methods=["GET"])
def extract_data():
    jobs.extract_tables_using_aws_textract.delay()
    return redirect('/')


# endpoint for deleting a job
@main_blueprint.route('/delete_job/<job_id>', methods=["GET"])
def deletejob(job_id):
    # get job from connected redis queue
    job = queue.fetch_job(job_id)
    # delete job
    job.delete()
    # redirect to job list page
    return redirect('/jobs')


# endpoint for getting a job
@main_blueprint.route("/jobs/<job_id>", methods=["GET"])
def get_status(job_id):
    # get job from connected redis queue
    job = queue.fetch_job(job_id)
    # process returned job and prepare response
    if job:
        response_object = {
            "status": "success",
            "data": {
                "job_id": job.get_id(),
                "job_status": job.get_status(),
                "job_result": job.result,
            },
        }
        status_code = 200
    else:
        response_object = {"message": "job not found"}
        status_code = 500
    return jsonify(response_object), status_code


@main_blueprint.route("/api/results",methods=["GET"])
def fetch_results():
    page = request.args.get('page', 1, type=int)
    tally = Tallying.query.paginate(page, 10, error_out=False).items
    return jsonify({"results":[tally_item.serialize() for tally_item in tally],
                    "page":page,
                    "total_results":len(Tallying.query.all())
                    })