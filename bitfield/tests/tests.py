import pickle

from django.db import connection, models
from django.db.models import F
from django.test import TestCase

from bitfield import BitHandler, Bit, BitField
from bitfield.tests import BitFieldTestModel, CompositeBitFieldTestModel, BitFieldTestModelForm

try:
    from django.db.models.expressions import ExpressionNode
    ExpressionNode.BITAND  # noqa
except AttributeError:
    # Django < 1.5
    def BITAND(a, b):
        return a & b

    def BITOR(a, b):
        return a | b
else:
    def BITAND(a, b):
        return a.bitand(b)

    def BITOR(a, b):
        return a.bitor(b)

try:
    from django.db.models.base import simple_class_factory  # noqa
except ImportError:
    # Django 1.5 muffed up the base class which breaks the pickle tests
    # Note, it's fixed again in 1.6.
    from django.db.models import base
    _model_unpickle = base.model_unpickle

    def simple_class_factory(model, attrs):
        return model

    def model_unpickle(model, attrs, factory):
        return _model_unpickle(model, attrs)
    setattr(base, 'simple_class_factory', simple_class_factory)
    setattr(base, 'model_unpickle', model_unpickle)


class BitHandlerTest(TestCase):
    def test_defaults(self):
        bithandler = BitHandler(0, ('FLAG_0', 'FLAG_1', 'FLAG_2', 'FLAG_3'))
        # Default value of 0.
        self.assertEquals(int(bithandler), 0)
        # Test bit numbers.
        self.assertEquals(int(bithandler.FLAG_0.number), 0)
        self.assertEquals(int(bithandler.FLAG_1.number), 1)
        self.assertEquals(int(bithandler.FLAG_2.number), 2)
        self.assertEquals(int(bithandler.FLAG_3.number), 3)
        # Negative test non-existant key.
        self.assertRaises(AttributeError, lambda: bithandler.FLAG_4)
        # Test bool().
        self.assertEquals(bool(bithandler.FLAG_0), False)
        self.assertEquals(bool(bithandler.FLAG_1), False)
        self.assertEquals(bool(bithandler.FLAG_2), False)
        self.assertEquals(bool(bithandler.FLAG_3), False)

    def test_nonzero_default(self):
        bithandler = BitHandler(1, ('FLAG_0', 'FLAG_1', 'FLAG_2', 'FLAG_3'))
        self.assertEquals(bool(bithandler.FLAG_0), True)
        self.assertEquals(bool(bithandler.FLAG_1), False)
        self.assertEquals(bool(bithandler.FLAG_2), False)
        self.assertEquals(bool(bithandler.FLAG_3), False)

        bithandler = BitHandler(2, ('FLAG_0', 'FLAG_1', 'FLAG_2', 'FLAG_3'))
        self.assertEquals(bool(bithandler.FLAG_0), False)
        self.assertEquals(bool(bithandler.FLAG_1), True)
        self.assertEquals(bool(bithandler.FLAG_2), False)
        self.assertEquals(bool(bithandler.FLAG_3), False)

        bithandler = BitHandler(3, ('FLAG_0', 'FLAG_1', 'FLAG_2', 'FLAG_3'))
        self.assertEquals(bool(bithandler.FLAG_0), True)
        self.assertEquals(bool(bithandler.FLAG_1), True)
        self.assertEquals(bool(bithandler.FLAG_2), False)
        self.assertEquals(bool(bithandler.FLAG_3), False)

        bithandler = BitHandler(4, ('FLAG_0', 'FLAG_1', 'FLAG_2', 'FLAG_3'))
        self.assertEquals(bool(bithandler.FLAG_0), False)
        self.assertEquals(bool(bithandler.FLAG_1), False)
        self.assertEquals(bool(bithandler.FLAG_2), True)
        self.assertEquals(bool(bithandler.FLAG_3), False)

    def test_mutation(self):
        bithandler = BitHandler(0, ('FLAG_0', 'FLAG_1', 'FLAG_2', 'FLAG_3'))
        self.assertEquals(bool(bithandler.FLAG_0), False)
        self.assertEquals(bool(bithandler.FLAG_1), False)
        self.assertEquals(bool(bithandler.FLAG_2), False)
        self.assertEquals(bool(bithandler.FLAG_3), False)

        bithandler = BitHandler(bithandler | 1, bithandler._keys)
        self.assertEquals(bool(bithandler.FLAG_0), True)
        self.assertEquals(bool(bithandler.FLAG_1), False)
        self.assertEquals(bool(bithandler.FLAG_2), False)
        self.assertEquals(bool(bithandler.FLAG_3), False)

        bithandler ^= 3
        self.assertEquals(int(bithandler), 2)

        self.assertEquals(bool(bithandler & 1), False)

        bithandler.FLAG_0 = False
        self.assertEquals(bithandler.FLAG_0, False)

        bithandler.FLAG_1 = True
        self.assertEquals(bithandler.FLAG_0, False)
        self.assertEquals(bithandler.FLAG_1, True)

        bithandler.FLAG_2 = False
        self.assertEquals(bithandler.FLAG_0, False)
        self.assertEquals(bithandler.FLAG_1, True)
        self.assertEquals(bithandler.FLAG_2, False)


class BitTest(TestCase):
    def test_int(self):
        bit = Bit(0)
        self.assertEquals(int(bit), 1)
        self.assertEquals(bool(bit), True)
        self.assertFalse(not bit)

    def test_comparison(self):
        self.assertEquals(Bit(0), Bit(0))
        self.assertNotEquals(Bit(1), Bit(0))
        self.assertNotEquals(Bit(0, 0), Bit(0, 1))
        self.assertEquals(Bit(0, 1), Bit(0, 1))
        self.assertEquals(Bit(0), 1)

    def test_and(self):
        self.assertEquals(1 & Bit(2), 0)
        self.assertEquals(1 & Bit(0), 1)
        self.assertEquals(1 & ~Bit(0), 0)
        self.assertEquals(Bit(0) & Bit(2), 0)
        self.assertEquals(Bit(0) & Bit(0), 1)
        self.assertEquals(Bit(0) & ~Bit(0), 0)

    def test_or(self):
        self.assertEquals(1 | Bit(2), 5)
        self.assertEquals(1 | Bit(5), 33)
        self.assertEquals(1 | ~Bit(2), -5)
        self.assertEquals(Bit(0) | Bit(2), 5)
        self.assertEquals(Bit(0) | Bit(5), 33)
        self.assertEquals(Bit(0) | ~Bit(2), -5)

    def test_xor(self):
        self.assertEquals(1 ^ Bit(2), 5)
        self.assertEquals(1 ^ Bit(0), 0)
        self.assertEquals(1 ^ Bit(1), 3)
        self.assertEquals(1 ^ Bit(5), 33)
        self.assertEquals(1 ^ ~Bit(2), -6)
        self.assertEquals(Bit(0) ^ Bit(2), 5)
        self.assertEquals(Bit(0) ^ Bit(0), 0)
        self.assertEquals(Bit(0) ^ Bit(1), 3)
        self.assertEquals(Bit(0) ^ Bit(5), 33)
        self.assertEquals(Bit(0) ^ ~Bit(2), -6)


class BitFieldTest(TestCase):
    def test_basic(self):
        # Create instance and make sure flags are working properly.
        instance = BitFieldTestModel.objects.create(flags=1)
        self.assertTrue(instance.flags.FLAG_0)
        self.assertFalse(instance.flags.FLAG_1)
        self.assertFalse(instance.flags.FLAG_2)
        self.assertFalse(instance.flags.FLAG_3)

    def test_regression_1425(self):
        # Creating new instances shouldn't allow negative values.
        instance = BitFieldTestModel.objects.create(flags=-1)
        self.assertEqual(instance.flags._value, 15)
        self.assertTrue(instance.flags.FLAG_0)
        self.assertTrue(instance.flags.FLAG_1)
        self.assertTrue(instance.flags.FLAG_2)
        self.assertTrue(instance.flags.FLAG_3)

        cursor = connection.cursor()
        flags_field = BitFieldTestModel._meta.get_field_by_name('flags')[0]
        flags_db_column = flags_field.db_column or flags_field.name
        cursor.execute("INSERT INTO %s (%s) VALUES (-1)" % (BitFieldTestModel._meta.db_table, flags_db_column))
        # There should only be the one row we inserted through the cursor.
        instance = BitFieldTestModel.objects.get(flags=-1)
        self.assertTrue(instance.flags.FLAG_0)
        self.assertTrue(instance.flags.FLAG_1)
        self.assertTrue(instance.flags.FLAG_2)
        self.assertTrue(instance.flags.FLAG_3)
        instance.save()

        self.assertEqual(BitFieldTestModel.objects.filter(flags=15).count(), 2)
        self.assertEqual(BitFieldTestModel.objects.filter(flags__lt=0).count(), 0)

    def test_select(self):
        BitFieldTestModel.objects.create(flags=3)
        self.assertTrue(BitFieldTestModel.objects.filter(flags=BitFieldTestModel.flags.FLAG_1).exists())
        self.assertTrue(BitFieldTestModel.objects.filter(flags=BitFieldTestModel.flags.FLAG_0).exists())
        self.assertFalse(BitFieldTestModel.objects.exclude(flags=BitFieldTestModel.flags.FLAG_0).exists())
        self.assertFalse(BitFieldTestModel.objects.exclude(flags=BitFieldTestModel.flags.FLAG_1).exists())

    def test_update(self):
        instance = BitFieldTestModel.objects.create(flags=0)
        self.assertFalse(instance.flags.FLAG_0)

        BitFieldTestModel.objects.filter(pk=instance.pk).update(flags=BITOR(F('flags'), BitFieldTestModel.flags.FLAG_1))
        instance = BitFieldTestModel.objects.get(pk=instance.pk)
        self.assertTrue(instance.flags.FLAG_1)

        BitFieldTestModel.objects.filter(pk=instance.pk).update(flags=BITOR(F('flags'), ((~BitFieldTestModel.flags.FLAG_0 | BitFieldTestModel.flags.FLAG_3))))
        instance = BitFieldTestModel.objects.get(pk=instance.pk)
        self.assertFalse(instance.flags.FLAG_0)
        self.assertTrue(instance.flags.FLAG_1)
        self.assertTrue(instance.flags.FLAG_3)
        self.assertFalse(BitFieldTestModel.objects.filter(flags=BitFieldTestModel.flags.FLAG_0).exists())

        BitFieldTestModel.objects.filter(pk=instance.pk).update(flags=BITAND(F('flags'), ~BitFieldTestModel.flags.FLAG_3))
        instance = BitFieldTestModel.objects.get(pk=instance.pk)
        self.assertFalse(instance.flags.FLAG_0)
        self.assertTrue(instance.flags.FLAG_1)
        self.assertFalse(instance.flags.FLAG_3)

    def test_update_with_handler(self):
        instance = BitFieldTestModel.objects.create(flags=0)
        self.assertFalse(instance.flags.FLAG_0)

        instance.flags.FLAG_1 = True

        BitFieldTestModel.objects.filter(pk=instance.pk).update(flags=BITOR(F('flags'), instance.flags))
        instance = BitFieldTestModel.objects.get(pk=instance.pk)
        self.assertTrue(instance.flags.FLAG_1)

    def test_negate(self):
        BitFieldTestModel.objects.create(flags=BitFieldTestModel.flags.FLAG_0 | BitFieldTestModel.flags.FLAG_1)
        BitFieldTestModel.objects.create(flags=BitFieldTestModel.flags.FLAG_1)
        self.assertEqual(BitFieldTestModel.objects.filter(flags=~BitFieldTestModel.flags.FLAG_0).count(), 1)
        self.assertEqual(BitFieldTestModel.objects.filter(flags=~BitFieldTestModel.flags.FLAG_1).count(), 0)
        self.assertEqual(BitFieldTestModel.objects.filter(flags=~BitFieldTestModel.flags.FLAG_2).count(), 2)

    def test_default_value(self):
        instance = BitFieldTestModel.objects.create()
        self.assertTrue(instance.flags.FLAG_0)
        self.assertTrue(instance.flags.FLAG_1)
        self.assertFalse(instance.flags.FLAG_2)
        self.assertFalse(instance.flags.FLAG_3)

    def test_binary_capacity(self):
        import math
        from django.db.models.fields import BigIntegerField
        # Local maximum value, slow canonical algorithm
        MAX_COUNT = int(math.floor(math.log(BigIntegerField.MAX_BIGINT, 2)))

        # Big flags list
        flags = ['f' + str(i) for i in range(100)]

        try:
            BitField(flags=flags[:MAX_COUNT])
        except ValueError:
            self.fail("It should work well with these flags")

        self.assertRaises(ValueError, BitField, flags=flags[:(MAX_COUNT + 1)])

    def test_dictionary_init(self):
        flags = {
            0: 'zero',
            1: 'first',
            10: 'tenth',
            2: 'second',

            'wrongkey': 'wrongkey',
            100: 'bigkey',
            -100: 'smallkey',
        }

        try:
            bf = BitField(flags)
        except ValueError:
            self.fail("It should work well with these flags")

        self.assertEquals(bf.flags, ['zero', 'first', 'second', '', '', '', '', '', '', '', 'tenth'])
        self.assertRaises(ValueError, BitField, flags={})
        self.assertRaises(ValueError, BitField, flags={'wrongkey': 'wrongkey'})
        self.assertRaises(ValueError, BitField, flags={'1': 'non_int_key'})

    def test_defaults_as_key_names(self):
        class TestModel(models.Model):
            flags = BitField(flags=(
                'FLAG_0',
                'FLAG_1',
                'FLAG_2',
                'FLAG_3',
            ), default=('FLAG_1', 'FLAG_2'))
        field = TestModel._meta.get_field('flags')
        self.assertEquals(field.default, TestModel.flags.FLAG_1 | TestModel.flags.FLAG_2)


class BitFieldSerializationTest(TestCase):
    def test_can_unserialize_bithandler(self):
        data = "cdjango.db.models.base\nmodel_unpickle\np0\n(cbitfield.tests.models\nBitFieldTestModel\np1\n(lp2\ncdjango.db.models.base\nsimple_class_factory\np3\ntp4\nRp5\n(dp6\nS'flags'\np7\nccopy_reg\n_reconstructor\np8\n(cbitfield.types\nBitHandler\np9\nc__builtin__\nobject\np10\nNtp11\nRp12\n(dp13\nS'_value'\np14\nI1\nsS'_keys'\np15\n(S'FLAG_0'\np16\nS'FLAG_1'\np17\nS'FLAG_2'\np18\nS'FLAG_3'\np19\ntp20\nsbsS'_state'\np21\ng8\n(cdjango.db.models.base\nModelState\np22\ng10\nNtp23\nRp24\n(dp25\nS'adding'\np26\nI00\nsS'db'\np27\nS'default'\np28\nsbsS'id'\np29\nI1\nsb."

        inst = pickle.loads(data)
        self.assertTrue(inst.flags.FLAG_0)
        self.assertFalse(inst.flags.FLAG_1)

    def test_pickle_integration(self):
        inst = BitFieldTestModel.objects.create(flags=1)
        data = pickle.dumps(inst)
        inst = pickle.loads(data)
        self.assertEquals(type(inst.flags), BitHandler)
        self.assertEquals(int(inst.flags), 1)

    def test_added_field(self):
        data = "cdjango.db.models.base\nmodel_unpickle\np0\n(cbitfield.tests.models\nBitFieldTestModel\np1\n(lp2\ncdjango.db.models.base\nsimple_class_factory\np3\ntp4\nRp5\n(dp6\nS'flags'\np7\nccopy_reg\n_reconstructor\np8\n(cbitfield.types\nBitHandler\np9\nc__builtin__\nobject\np10\nNtp11\nRp12\n(dp13\nS'_value'\np14\nI1\nsS'_keys'\np15\n(S'FLAG_0'\np16\nS'FLAG_1'\np17\nS'FLAG_2'\np18\ntp19\nsbsS'_state'\np20\ng8\n(cdjango.db.models.base\nModelState\np21\ng10\nNtp22\nRp23\n(dp24\nS'adding'\np25\nI00\nsS'db'\np27\nS'default'\np27\nsbsS'id'\np28\nI1\nsb."

        inst = pickle.loads(data)
        self.assertTrue('FLAG_3' in inst.flags.keys())


class CompositeBitFieldTest(TestCase):
    def test_get_flag(self):
        inst = CompositeBitFieldTestModel()
        self.assertEqual(inst.flags.FLAG_0, inst.flags_1.FLAG_0)
        self.assertEqual(inst.flags.FLAG_4, inst.flags_2.FLAG_4)
        self.assertRaises(AttributeError, lambda: inst.flags.flag_NA)

    def test_set_flag(self):
        inst = CompositeBitFieldTestModel()

        flag_0_original = bool(inst.flags.FLAG_0)
        self.assertEqual(bool(inst.flags_1.FLAG_0), flag_0_original)
        flag_4_original = bool(inst.flags.FLAG_4)
        self.assertEqual(bool(inst.flags_2.FLAG_4), flag_4_original)

        # flip flags' bits
        inst.flags.FLAG_0 = not flag_0_original
        inst.flags.FLAG_4 = not flag_4_original

        # check to make sure the bit flips took effect
        self.assertNotEqual(bool(inst.flags.FLAG_0), flag_0_original)
        self.assertNotEqual(bool(inst.flags_1.FLAG_0), flag_0_original)
        self.assertNotEqual(bool(inst.flags.FLAG_4), flag_4_original)
        self.assertNotEqual(bool(inst.flags_2.FLAG_4), flag_4_original)

        def set_flag():
            inst.flags.flag_NA = False
        self.assertRaises(AttributeError, set_flag)

    def test_hasattr(self):
        inst = CompositeBitFieldTestModel()
        self.assertEqual(hasattr(inst.flags, 'flag_0'),
            hasattr(inst.flags_1, 'flag_0'))
        self.assertEqual(hasattr(inst.flags, 'flag_4'),
            hasattr(inst.flags_2, 'flag_4'))


class BitFormFieldTest(TestCase):
    def test_form_new_invalid(self):
        invalid_data_dicts = [
            {'flags': ['FLAG_0', 'FLAG_FLAG']},
            {'flags': ['FLAG_4']},
            {'flags': [1, 2]}
        ]
        for invalid_data in invalid_data_dicts:
            form = BitFieldTestModelForm(data=invalid_data)
            self.assertFalse(form.is_valid())

    def test_form_new(self):
        data_dicts = [
            {'flags': ['FLAG_0', 'FLAG_1']},
            {'flags': ['FLAG_3']},
            {'flags': []},
            {}
        ]
        for data in data_dicts:
            form = BitFieldTestModelForm(data=data)
            self.failUnless(form.is_valid())
            instance = form.save()
            flags = data['flags'] if 'flags' in data else []
            for k in BitFieldTestModel.flags:
                self.assertEquals(bool(getattr(instance.flags, k)), k in flags)

    def test_form_update(self):
        instance = BitFieldTestModel.objects.create(flags=0)
        for k in BitFieldTestModel.flags:
            self.assertFalse(bool(getattr(instance.flags, k)))

        data = {'flags': ['FLAG_0', 'FLAG_1']}
        form = BitFieldTestModelForm(data=data, instance=instance)
        self.failUnless(form.is_valid())
        instance = form.save()
        for k in BitFieldTestModel.flags:
            self.assertEquals(bool(getattr(instance.flags, k)), k in data['flags'])

        data = {'flags': ['FLAG_2', 'FLAG_3']}
        form = BitFieldTestModelForm(data=data, instance=instance)
        self.failUnless(form.is_valid())
        instance = form.save()
        for k in BitFieldTestModel.flags:
            self.assertEquals(bool(getattr(instance.flags, k)), k in data['flags'])

        data = {'flags': []}
        form = BitFieldTestModelForm(data=data, instance=instance)
        self.failUnless(form.is_valid())
        instance = form.save()
        for k in BitFieldTestModel.flags:
            self.assertFalse(bool(getattr(instance.flags, k)))
