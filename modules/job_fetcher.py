"""
job_fetcher.py — 9 sources: JobSpy(Indeed+Google), Remotive, Adzuna,
Naukri, Monster, Greenhouse(50+ companies), Lever(30+ companies), Wellfound, LinkedIn
"""
import os, json, logging, requests, time
from datetime import datetime, timezone
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

GREENHOUSE_COMPANIES = [
    "freshworks","meesho","browserstack","postman","druva","hasura","chargebee","phonepe","groww","nykaa","juspay","vinculum","unicommerce","servicenow","workday","coupa","celonis",
    "kissflow","leadsquared","darwinbox","zomentum","exotel","sprinklr","clevertap",
    "project44","fourkites","coupa","shipbob","loadsmart",
    "atlassian","gitlab","notion","linear","loom","airtable","intercom","hubspot",
    "twilio","stripe","figma","miro","contentful","algolia","elastic","hashicorp",
    "confluent","datadog","pagerduty","brex","rippling","lattice","culture-amp",
]
LEVER_COMPANIES = [
    "razorpay","cred","khatabook","udaan","spinny","slice","jupiter","smallcase","swiggy","zeta-tech","zepto","setu",
    "flexport","transfix","convoy",
    "airbnb","coinbase","plaid","carta","gusto","deel","remote","andela",
    "canva","zendesk","cloudflare","segment","mixpanel",
]

def make_job(title,company,location,job_url,description,date_posted,salary_text,source,apply_url=None):
    return {"id":None,"title":title,"company":company,"location":location,
            "job_url":job_url,"apply_url":apply_url or job_url,"apply_email":None,
            "description":(description or "")[:8000],
            "date_posted":date_posted.isoformat() if isinstance(date_posted,datetime) else date_posted,
            "salary_text":salary_text or "","source":source,
            "score":None,"cover_letter":None,"status":"found",
            "apply_platform":None,"applied_at":None,
            "fetched_at":datetime.now(timezone.utc).isoformat(),
            "glassdoor_rating":None}

def is_title_relevant(title):
    kws=["program manager","programme manager","project manager","project lead",
         "product manager","senior pm","sr pm","principal pm","technical program","tpm",
         "operations manager","supply chain","logistics manager","delivery manager",
         "engagement manager","portfolio manager","business analyst","strategy manager",
         "transformation","consulting manager","scrum master"]
    t=(title or "").lower()
    return any(k in t for k in kws)

# ── 1. JobSpy (Indeed + Google) ───────────────────────────────────────────────
def fetch_via_jobspy(keywords, prefs):
    try:
        from jobspy import scrape_jobs
    except ImportError:
        return []
    sites  = prefs["job_boards"]["jobspy"]["sites"]
    n      = prefs["job_boards"]["jobspy"].get("results_per_keyword",20)
    age    = prefs["job_preferences"]["max_job_age_days"]
    jobs   = []
    for kw in keywords:
        try:
            df = scrape_jobs(site_name=sites,search_term=kw,location="Remote",
                             results_wanted=n,hours_old=age*24)
            for _,row in df.iterrows():
                dp=None
                try:
                    if row.get("date_posted") and str(row["date_posted"])!="NaT":
                        dp=datetime.fromisoformat(str(row["date_posted"]))
                except: pass
                sal=""
                if row.get("min_amount"):
                    sal=f"{row.get('currency','')} {row['min_amount']:,.0f}"
                    if row.get("max_amount"): sal+=f" – {row['max_amount']:,.0f}"
                jobs.append(make_job(str(row.get("title","")),str(row.get("company","")),
                    str(row.get("location","Remote")),str(row.get("job_url","")),
                    str(row.get("description","")),dp,sal,str(row.get("site","jobspy")),
                    str(row.get("job_url_direct") or row.get("job_url",""))))
        except Exception as e:
            logger.error(f"[JobSpy] '{kw}': {e}")
    logger.info(f"[JobSpy] {len(jobs)}")
    return jobs

# ── 2. LinkedIn (single keyword, 90s timeout) ─────────────────────────────────
def _linkedin_inner(prefs):
    from jobspy import scrape_jobs
    cfg=prefs["job_boards"].get("linkedin",{})
    kw=cfg.get("keyword","Senior Program Manager remote")
    df=scrape_jobs(site_name=["linkedin"],search_term=kw,location="Remote",
                   results_wanted=cfg.get("results_wanted",20),
                   hours_old=prefs["job_preferences"]["max_job_age_days"]*24,
                   linkedin_fetch_description=False)
    jobs=[]
    for _,row in df.iterrows():
        dp=None
        try: dp=datetime.fromisoformat(str(row["date_posted"]))
        except: pass
        jobs.append(make_job(str(row.get("title","")),str(row.get("company","")),
            str(row.get("location","Remote")),str(row.get("job_url","")),
            str(row.get("description","")),dp,"","linkedin",str(row.get("job_url",""))))
    return jobs

def fetch_via_linkedin(prefs):
    from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutTimeout
    cfg=prefs["job_boards"].get("linkedin",{})
    timeout=cfg.get("timeout_seconds",90)
    try:
        with ThreadPoolExecutor(max_workers=1) as ex:
            jobs=ex.submit(_linkedin_inner,prefs).result(timeout=timeout)
        logger.info(f"[LinkedIn] {len(jobs)}")
        return jobs
    except FutTimeout:
        logger.warning("[LinkedIn] Timed out — skipping")
        return []
    except Exception as e:
        logger.error(f"[LinkedIn] {e}")
        return []

# ── 3. Remotive ───────────────────────────────────────────────────────────────
@retry(stop=stop_after_attempt(2),wait=wait_exponential(min=2,max=8))
def fetch_via_remotive(prefs):
    base=prefs["job_boards"]["remotive"]["base_url"]
    jobs=[]
    for term in ["program manager","project manager","product manager"]:
        try:
            r=requests.get(base,params={"search":term,"limit":50},timeout=15)
            r.raise_for_status()
            for item in r.json().get("jobs",[]):
                if not is_title_relevant(item.get("title","")): continue
                dp=None
                try: dp=datetime.fromisoformat(item["publication_date"].replace("Z","+00:00"))
                except: pass
                jobs.append(make_job(item.get("title",""),item.get("company_name",""),
                    item.get("candidate_required_location","Worldwide"),
                    item.get("url",""),item.get("description",""),dp,item.get("salary",""),"remotive"))
        except Exception as e:
            logger.error(f"[Remotive] '{term}': {e}")
    logger.info(f"[Remotive] {len(jobs)}")
    return jobs

# ── 4. Adzuna ─────────────────────────────────────────────────────────────────
@retry(stop=stop_after_attempt(2),wait=wait_exponential(min=2,max=8))
def fetch_via_adzuna(prefs):
    app_id=os.getenv("ADZUNA_APP_ID"); app_key=os.getenv("ADZUNA_APP_KEY")
    if not app_id or not app_key: return []
    jobs=[]
    for kw in ["Senior Program Manager","Senior Project Manager","Technical Program Manager"]:
        try:
            r=requests.get(f"https://api.adzuna.com/v1/api/jobs/in/search/1",
                params={"app_id":app_id,"app_key":app_key,"results_per_page":30,
                        "what":kw,"title_only":kw},timeout=15)
            r.raise_for_status()
            for item in r.json().get("results",[]):
                if not is_title_relevant(item.get("title","")): continue
                dp=None
                try: dp=datetime.fromisoformat(item["created"].replace("Z","+00:00"))
                except: pass
                sal=f"₹ {item['salary_min']:,.0f}–{item.get('salary_max',0):,.0f}" if item.get("salary_min") else ""
                jobs.append(make_job(item.get("title",""),item.get("company",{}).get("display_name",""),
                    item.get("location",{}).get("display_name","India"),
                    item.get("redirect_url",""),item.get("description",""),dp,sal,"adzuna"))
        except Exception as e:
            logger.error(f"[Adzuna] '{kw}': {e}")
    logger.info(f"[Adzuna] {len(jobs)}")
    return jobs

# ── 5. Naukri ─────────────────────────────────────────────────────────────────
def fetch_via_naukri(prefs):
    headers={"User-Agent":"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
             "Accept":"application/json","appid":"109","systemid":"109",
             "Referer":"https://www.naukri.com/"}
    jobs=[]
    for kw,loc in [("senior program manager",""),("senior project manager",""),
                   ("program manager","work from home")]:
        try:
            r=requests.get("https://www.naukri.com/jobapi/v3/search",
                headers=headers,
                params={"noOfResults":20,"urlType":"search_by_key_loc","searchType":"adv",
                        "keyword":kw,"sort":"r","experience":5,"location":loc,"qp":1},
                timeout=15)
            if r.status_code!=200: continue
            for item in r.json().get("jobDetails",[]):
                if not is_title_relevant(item.get("title","")): continue
                dp=None
                if item.get("createdDate"):
                    try: dp=datetime.fromtimestamp(item["createdDate"]/1000,tz=timezone.utc)
                    except: pass
                url=f"https://www.naukri.com{item.get('jdURL','')}" if item.get("jdURL") else ""
                jobs.append(make_job(item.get("title",""),item.get("companyName",""),
                    "India / Remote",url,item.get("jobDescription",""),dp,item.get("salary",""),"naukri"))
        except Exception as e:
            logger.error(f"[Naukri] '{kw}': {e}")
        time.sleep(1)
    logger.info(f"[Naukri] {len(jobs)}")
    return jobs

# ── 6. Monster ────────────────────────────────────────────────────────────────
def fetch_via_monster(prefs):
    jobs=[]
    for kw in ["Senior Program Manager","Senior Project Manager"]:
        try:
            r=requests.get("https://appsapi.monster.io/jobs-svx-service/v2/monster/search-jobs/samsearch/en-IN",
                params={"apikey":"2e7af2cd-d67c-4214-b84c-dca1e1f3dfa4","q":kw,
                        "where":"India","jobtype":"permanent","hits_per_page":20,"page":0},
                headers={"User-Agent":"Mozilla/5.0"},timeout=15)
            if r.status_code!=200: continue
            for item in r.json().get("hits",{}).get("hits",[]):
                src=item.get("_source",{})
                if not is_title_relevant(src.get("title","")): continue
                dp=None
                try: dp=datetime.fromisoformat(src.get("dateRecency","").replace("Z","+00:00"))
                except: pass
                jobs.append(make_job(src.get("title",""),src.get("company",{}).get("name",""),
                    src.get("city","India"),src.get("jobUrl",""),src.get("body",""),dp,"","monster",
                    src.get("applyUrl") or src.get("jobUrl","")))
        except Exception as e:
            logger.error(f"[Monster] '{kw}': {e}")
    logger.info(f"[Monster] {len(jobs)}")
    return jobs

# ── 7. Greenhouse (50+ company career pages) ──────────────────────────────────
def fetch_via_greenhouse(prefs):
    jobs=[]
    for co in GREENHOUSE_COMPANIES:
        try:
            r=requests.get(f"https://boards.greenhouse.io/embed/job_board/jobs?for={co}&content=true",timeout=10)
            if r.status_code!=200: continue
            for item in r.json().get("jobs",[]):
                if not is_title_relevant(item.get("title","")): continue
                dp=None
                try: dp=datetime.fromisoformat(item.get("updated_at","").replace("Z","+00:00"))
                except: pass
                jobs.append(make_job(item.get("title",""),co.replace("-"," ").title(),
                    item.get("location",{}).get("name","Remote"),
                    item.get("absolute_url",""),item.get("content","")[:8000],
                    dp,"",f"greenhouse/{co}",item.get("absolute_url","")))
        except Exception as e:
            logger.debug(f"[Greenhouse] {co}: {e}")
        time.sleep(0.2)
    logger.info(f"[Greenhouse] {len(jobs)} from {len(GREENHOUSE_COMPANIES)} companies")
    return jobs

# ── 8. Lever (30+ company career pages) ──────────────────────────────────────
def fetch_via_lever(prefs):
    jobs=[]
    for co in LEVER_COMPANIES:
        try:
            r=requests.get(f"https://api.lever.co/v0/postings/{co}?mode=json",timeout=10)
            if r.status_code!=200: continue
            for item in r.json():
                if not is_title_relevant(item.get("text","")): continue
                dp=None
                if item.get("createdAt"):
                    try: dp=datetime.fromtimestamp(item["createdAt"]/1000,tz=timezone.utc)
                    except: pass
                loc=item.get("categories",{}).get("location","Remote")
                desc=(item.get("descriptionPlain","") or item.get("description",""))
                jobs.append(make_job(item.get("text",""),co.replace("-"," ").title(),
                    loc,item.get("hostedUrl",""),desc[:8000],dp,"",f"lever/{co}",
                    item.get("applyUrl","") or item.get("hostedUrl","")))
        except Exception as e:
            logger.debug(f"[Lever] {co}: {e}")
        time.sleep(0.2)
    logger.info(f"[Lever] {len(jobs)} from {len(LEVER_COMPANIES)} companies")
    return jobs

# ── 9. Wellfound ──────────────────────────────────────────────────────────────
def fetch_via_wellfound(prefs):
    jobs=[]
    try:
        r=requests.get("https://angel.co/api/1/jobs",
            params={"roles[]":["operations_manager","product_manager"],"job_types[]":"full-time","remote":True,"page":1},
            headers={"User-Agent":"Mozilla/5.0"},timeout=15)
        if r.status_code==200:
            for item in r.json().get("jobs",[]):
                if not is_title_relevant(item.get("title","")): continue
                startup=item.get("startup",{})
                dp=None
                try: dp=datetime.fromisoformat(item.get("created_at","").replace("Z","+00:00"))
                except: pass
                jobs.append(make_job(item.get("title",""),startup.get("name",""),
                    (item.get("locations",["Remote"])[0] if item.get("locations") else "Remote"),
                    item.get("job_url",""),item.get("description",""),dp,item.get("salary",""),"wellfound"))
    except Exception as e:
        logger.error(f"[Wellfound] {e}")
    logger.info(f"[Wellfound] {len(jobs)}")
    return jobs

# ── Main ──────────────────────────────────────────────────────────────────────
def fetch_all_jobs(profile, prefs):
    keywords=profile.get("keywords_for_search",["Senior Program Manager remote"])
    all_jobs=[]
    boards=prefs.get("job_boards",{})

    if boards.get("jobspy",{}).get("enabled"):
        all_jobs.extend(fetch_via_jobspy(keywords,prefs))
    if boards.get("remotive",{}).get("enabled"):
        all_jobs.extend(fetch_via_remotive(prefs))
    if boards.get("adzuna",{}).get("enabled"):
        all_jobs.extend(fetch_via_adzuna(prefs))

    logger.info("[Fetcher] Fetching Naukri...")
    all_jobs.extend(fetch_via_naukri(prefs))
    logger.info("[Fetcher] Fetching Monster...")
    all_jobs.extend(fetch_via_monster(prefs))
    logger.info("[Fetcher] Fetching Greenhouse career pages (50 companies)...")
    all_jobs.extend(fetch_via_greenhouse(prefs))
    logger.info("[Fetcher] Fetching Lever career pages (25 companies)...")
    all_jobs.extend(fetch_via_lever(prefs))
    logger.info("[Fetcher] Fetching Wellfound...")
    all_jobs.extend(fetch_via_wellfound(prefs))

    if boards.get("linkedin_enabled"):
        logger.info("[Fetcher] Fetching LinkedIn (90s timeout)...")
        all_jobs.extend(fetch_via_linkedin(prefs))

    logger.info(f"[Fetcher] Grand total: {len(all_jobs)} from all sources")
    return all_jobs
