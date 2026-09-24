"""Validated dataset identifiers, independent of the crop ontology."""

import re


def validate_dataset_prefix(value):
    if not isinstance(value, str) or not re.fullmatch(r'[a-z][a-z0-9_]{0,31}', value):
        raise ValueError('dataset_prefix 必须为小写字母开头、最长 32 字符的小写 ASCII 字母、数字或下划线标识')
    return value


def effective_dataset_prefix(profile):
    """Only a missing field uses the legacy crop name; explicit invalid values fail."""
    return validate_dataset_prefix(profile['dataset_prefix'] if 'dataset_prefix' in profile else profile.get('crop'))
