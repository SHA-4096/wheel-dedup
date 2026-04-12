import pytest

from wheel_dedup.parser import normalize, parse_wheel, WheelInfo


class TestNormalize:
    def test_underscores(self):
        assert normalize("my_package") == "my-package"

    def test_dots(self):
        assert normalize("my.package") == "my-package"

    def test_mixed_separators(self):
        assert normalize("My_Package.Name") == "my-package-name"

    def test_consecutive_separators(self):
        assert normalize("my__package") == "my-package"

    def test_already_normalized(self):
        assert normalize("my-package") == "my-package"

    def test_case_insensitive(self):
        assert normalize("MyPackage") == "mypackage"


class TestParseWheel:
    def test_standard_wheel(self):
        info = parse_wheel("numpy-1.24.0-cp311-cp311-linux_x86_64.whl")
        assert info.distribution == "numpy"
        assert info.version == "1.24.0"
        assert info.filename == "numpy-1.24.0-cp311-cp311-linux_x86_64.whl"
        assert info.normalized_name == "numpy"

    def test_underscore_in_name(self):
        info = parse_wheel("my_package-2.0.0-py3-none-any.whl")
        assert info.distribution == "my_package"
        assert info.normalized_name == "my-package"

    def test_with_build_tag(self):
        info = parse_wheel("foo-1.0.0-1-py3-none-any.whl")
        assert info.distribution == "foo"
        assert info.version == "1.0.0"

    def test_full_path(self):
        info = parse_wheel("/tmp/wheels/requests-2.28.0-py3-none-any.whl")
        assert info.distribution == "requests"
        assert info.filename == "requests-2.28.0-py3-none-any.whl"
        assert info.path == "/tmp/wheels/requests-2.28.0-py3-none-any.whl"

    def test_invalid_filename(self):
        with pytest.raises(ValueError, match="Invalid wheel filename"):
            parse_wheel("not-a-wheel.tar.gz")

    def test_complex_version(self):
        info = parse_wheel("pkg-1.2.3rc1-py3-none-any.whl")
        assert info.version == "1.2.3rc1"
