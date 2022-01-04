# Copyright 2017 The TensorFlow Authors. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ==============================================================================
"""Tests the Tensorboard images plugin."""


import collections.abc
import json

from pathlib import Path
import tensorflow as tf
from werkzeug import test as werkzeug_test
from werkzeug import wrappers

from tensorboard.backend import application
from tensorboard.backend.event_processing import data_provider
from tensorboard.backend.event_processing import (
    plugin_event_multiplexer as event_multiplexer,
)
from tensorboard.plugins import base_plugin
from tensorboard_plugin_3d import plugin as tb_3d_plugin
from tensorflow.python.framework import test_util

tf.compat.v1.disable_v2_behavior()


@test_util.run_all_in_graph_and_eager_modes
class Tensorboard3DPluginTest(tf.test.TestCase):
    def setUp(self):
        super().setUp()
        logdir, multiplexer = self._gather_data()
        provider = data_provider.MultiplexerDataProvider(multiplexer, logdir)
        ctx = base_plugin.TBContext(logdir=logdir, data_provider=provider)
        self.plugin = tb_3d_plugin.TensorboardPlugin3D(ctx)
        wsgi_app = application.TensorBoardWSGI([self.plugin])
        self.server = werkzeug_test.Client(wsgi_app, wrappers.Response)
        self.routes = self.plugin.get_plugin_apps()

    def _gather_data(self):
        """Point to data on disk, returning `(logdir, multiplexer)`."""
        self.log_dir = Path('./data')

        # Start a server with the plugin.
        multiplexer = event_multiplexer.EventMultiplexer(
            {
                "transform": f'{self.log_dir}/transform',
                "unet": f'{self.log_dir}/unet',
            }
        )
        multiplexer.Reload()
        return self.log_dir, multiplexer

    def testServeFrontend(self):
        serve_static_file = self.plugin._serve_static_file
        client = werkzeug_test.Client(serve_static_file, wrappers.Response)
        response = client.get('/data/plugin/tensorboard_plugin_3d/static/index.js')
        self.assertEqual(200, response.status_code)

    def testPluginVisibility(self):
        visible = self.plugin.is_active()
        self.assertTrue(visible)

    def _DeserializeResponse(self, byte_content):
        """Deserializes byte content that is a JSON encoding.

        Args:
          byte_content: The byte content of a response.

        Returns:
          The deserialized python object decoded from JSON.
        """
        return json.loads(byte_content.decode("utf-8"))

    def testRoutesProvided(self):
        """Tests that the plugin offers the correct routes."""
        self.assertIsInstance(self.routes["/index.js"], collections.abc.Callable)
        self.assertIsInstance(self.routes["/index.html"], collections.abc.Callable)
        self.assertIsInstance(self.routes["/images"], collections.abc.Callable)
        self.assertIsInstance(self.routes["/tags"], collections.abc.Callable)


    def testNewStyleImagesRouteEager(self):
        """Tests that the /images routes returns correct data."""
        self.plugin.is_active()
        response = self.server.get("/data/plugin/tensorboard_plugin_3d/images")
        self.assertEqual(200, response.status_code)

        # Verify that the correct entries are returned.
        entries = self._DeserializeResponse(response.get_data())
        self.assertEqual(13, len(entries['images']))

    def testRunsRoute(self):
        """Tests that the /runs route offers the correct run to tag mapping."""
        response = self.server.get("/data/plugin/tensorboard_plugin_3d/tags")
        self.assertEqual(200, response.status_code)
        self.assertDictEqual(
            {
                "transform": ["output_HWD/image"],
                "unet": ["input_0_HWD/image", "input_1_HWD/image", "output_HWD/image"],
            },
            self._DeserializeResponse(response.get_data()),
        )


if __name__ == "__main__":
    tf.test.main()
