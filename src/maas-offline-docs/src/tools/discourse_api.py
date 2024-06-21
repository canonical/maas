import requests
import sys
import time


class DiscourseAPI:
    def __init__(self, config):
        self.base_url = config.get("base_url")
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({"Api-Key": config["api_key"]})

    def call_api(self, endpoint):
        while True:
            response = self.session.get(self.base_url + endpoint)
            if response.status_code == 429:  # handle rate-limited access
                wait_seconds = response.json()["wait_seconds"]
                time.sleep(wait_seconds)
            else:
                response.raise_for_status()
                return response.json()

    def get_post(self, post_id):
        return self.call_api(f"/posts/{post_id}.json")

    def get_markdown(self, topic_number):
        try:
            topic_json = self.get_topic(topic_number)
            post_id = topic_json["post_stream"]["posts"][0]["id"]
            post_json = self.get_post(post_id)
            return post_json["raw"]
        except KeyError as e:
            sys.exit(f"A KeyError occurred: {e}")
        except Exception as e:
            sys.exit(f"An error occurred: {e}")

    def get_raw(self, topic_number):
        try:
            topic_json = self.get_topic(topic_number)
            return topic_json;
        except KeyError as e:
            sys.exit(f"A KeyError occurred: {e}")
        except Exception as e:
            sys.exit(f"An error occurred: {e}")

    def get_title(self, topic_number):
        try:
            topic_json = self.get_topic(topic_number)
            topic_title = topic_json["fancy_title"]
            return topic_title
        except KeyError as e:
            sys.exit(f"A KeyError occurred: {e}")
        except Exception as e:
            sys.exit(f"An error occurred: {e}")

    def get_topic(self, topic_id):
        return self.call_api(f"/t/{topic_id}.json")

    def get_topic_last_edit_timestamp(self, topic_id):
        topic = self.get_topic(topic_id)
        last_edit_timestamp = topic.get("last_posted_at")
        return last_edit_timestamp

    def post_to_topic(self, topic_id, markdown_content):
        topic_json = self.get_topic(topic_id)
        post_id = topic_json["post_stream"]["posts"][0]["id"]
        endpoint = "/posts/" + str(post_id) + ".json"
        payload = {
            "topic_id": topic_id,
            "raw": markdown_content,
        }
        response = self.session.post(self.base_url + endpoint, json=payload)
        response.raise_for_status()

    def update_topic_content(self, topic_id, markdown_content):
        # Fetch the existing topic data
        topic_endpoint = f"/t/{topic_id}.json"
        topic_data = self.call_api(topic_endpoint)

        # Update the existing content
        post_id = topic_data["post_stream"]["posts"][0]["id"]
        post_endpoint = f"/posts/{post_id}.json"
        post_data = self.call_api(post_endpoint)
        post_data["raw"] = markdown_content

        # Update the post with the modified content
        update_response = self.session.put(
            self.base_url + post_endpoint, json=post_data
        )
        update_response.raise_for_status()
        return update_response.status_code
    
