"""Optional task status and submission tools inside the existing panel login."""

import json
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

import streamlit as st


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def render_queue_panel(endpoint, token):
    st.header("Kalıcı Görev Kuyruğu")
    if not endpoint or not token:
        st.info("Kalıcı kuyruk bağlantısı henüz yapılandırılmadı.")
        return
    try:
        url = urlsplit(endpoint)
        if url.scheme != "https" or not url.hostname or url.username or url.password or url.query or url.fragment:
            raise ValueError()
    except ValueError:
        st.error("Kuyruk adresi bir HTTPS servis adresi olmalı.")
        return

    def call(path, data=None, key=None):
        headers = {"Authorization": "Bearer " + token}
        if data is not None:
            headers.update({"Content-Type": "application/json", "Idempotency-Key": key})
        request = Request(endpoint.rstrip("/") + path, headers=headers, data=data)
        with build_opener(NoRedirect()).open(request, timeout=8) as response:
            return json.load(response)

    with st.form("vortex_durable_queue"):
        key = st.text_input("İstek anahtarı", max_chars=128)
        title = st.text_input("Kuyruk görevi başlığı", max_chars=200)
        brief = st.text_area("Kuyruk görevi metni", max_chars=6000)
        if st.form_submit_button("Kuyruğa ekle"):
            try:
                result = call("/jobs", json.dumps({"title": title, "brief": brief}).encode(), key)
                st.session_state["vortex_task_queue_id"] = result["id"]
            except HTTPError as exc:
                st.error("Gönderim reddedildi. HTTP " + str(exc.code))
            except (URLError, TimeoutError, ValueError):
                st.error("Kuyruk servisine ulaşılamadı.")

    job_id = st.text_input("Durum için görev kimliği", key="vortex_task_queue_id", max_chars=32)
    if st.button("Görev durumunu getir"):
        if not re.fullmatch(r"[a-f0-9]{32}", job_id):
            st.warning("Geçerli bir görev kimliği gir.")
            return
        try:
            job = call("/jobs/" + job_id)
            st.write(f"Durum: {job['status']} · Deneme: {job['attempt']}")
            if job["result"] is not None:
                st.json(job["result"])
        except HTTPError as exc:
            st.error("Görev alınamadı. HTTP " + str(exc.code))
        except (URLError, TimeoutError, ValueError):
            st.error("Kuyruk servisine ulaşılamadı.")
