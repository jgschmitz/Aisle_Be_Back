"""Offline checks; no credentials, paid calls, or database writes."""
import asyncio
import json
from pathlib import Path
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from common import money_to_cents, build_document, save_observation, viam_action


class ExamplesTest(unittest.TestCase):
    def test_exact_money(self):
        self.assertEqual(money_to_cents('4.99'), 499)
        self.assertEqual(money_to_cents('0.01'), 1)
        for value in ('2 for $5', 'NaN', '-1', '1.234', '4,99', ''):
            with self.subTest(value=value), self.assertRaises(ValueError):
                money_to_cents(value)

    def test_image_and_currency_validation(self):
        payload = json.loads(Path('captures/sample.label.json').read_text())
        image = Path('captures/sample.jpg').read_bytes()
        doc = build_document(payload, image)
        self.assertEqual(doc['price']['amount_minor'], 499)
        self.assertIsNotNone(doc['captured_at'].tzinfo)
        with self.assertRaises(ValueError):
            build_document(payload, image + b'changed')
        payload['label']['currency'] = 'EUR'
        with self.assertRaises(ValueError):
            build_document(payload, image)

    def test_retry_does_not_replace_observation(self):
        collection = MagicMock()
        collection.update_one.return_value.upserted_id = 'stable-id'
        client = MagicMock()
        client.__enter__.return_value.__getitem__.return_value.__getitem__.return_value = collection
        doc = {'_id': 'stable-id', 'price': {'amount_minor': 499}}
        with patch('common.mongo_client', return_value=client):
            self.assertTrue(save_observation('unused', 'demo', doc))
            collection.update_one.return_value.upserted_id = None
            self.assertFalse(save_observation('unused', 'demo', doc))
        collection.update_one.assert_called_with({'_id': 'stable-id'}, {'$setOnInsert': doc}, upsert=True)

    def test_current_viam_capture_closes_connection(self):
        from viam.media.video import NamedImage, CameraMimeType
        frame = NamedImage('color', Path('captures/sample.jpg').read_bytes(), CameraMimeType.JPEG)
        camera = MagicMock(spec=['get_images'])
        camera.get_images = AsyncMock(return_value=([frame], None))
        robot = MagicMock()
        robot.close = AsyncMock()
        with patch('viam.robot.client.RobotClient.at_address', new=AsyncMock(return_value=robot)), \
             patch('viam.components.camera.Camera.from_robot', return_value=camera):
            image = asyncio.run(viam_action('test', '00000000-0000-4000-8000-000000000001', 'key', 'camera'))
        self.assertTrue(image.startswith(b'\xff\xd8'))
        robot.close.assert_awaited_once()

    def test_viam_failure_closes_connection(self):
        camera = MagicMock(spec=['get_images'])
        camera.get_images = AsyncMock(side_effect=RuntimeError('camera offline'))
        robot = MagicMock()
        robot.close = AsyncMock()
        with patch('viam.robot.client.RobotClient.at_address', new=AsyncMock(return_value=robot)), \
             patch('viam.components.camera.Camera.from_robot', return_value=camera):
            with self.assertRaises(RuntimeError):
                asyncio.run(viam_action('test', '00000000-0000-4000-8000-000000000001', 'key', 'camera'))
        robot.close.assert_awaited_once()


if __name__ == '__main__':
    unittest.main()
