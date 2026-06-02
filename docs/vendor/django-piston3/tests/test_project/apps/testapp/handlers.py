from django.core.paginator import Paginator

from piston3.handler import BaseHandler
from piston3.utils import (
    rc,
    validate,
)
from test_project.apps.testapp import signals

from .forms import (
    EchoForm,
    FormWithFileField,
)
from .models import (
    CircularA,
    CircularB,
    CircularC,
    Comment,
    ConditionalFieldsModel,
    ExpressiveSampleModel,
    InheritedModel,
    Issue58Model,
    ListFieldsModel,
    PlainOldObject,
    SampleModel,
)


class EntryHandler(BaseHandler):
    model = SampleModel
    allowed_methods = (
        "GET",
        "PUT",
        "POST",
    )

    @classmethod
    def resource_uri(cls, obj):
        return "entry", [obj.pk]

    def read(self, request, pk=None):
        signals.entry_request_started.send(sender=self, request=request)
        if pk is not None:
            return SampleModel.objects.get(pk=int(pk))
        paginator = Paginator(SampleModel.objects.all(), 25)
        return paginator.page(int(request.GET.get("page", 1))).object_list

    def update(self, request, pk):
        signals.entry_request_started.send(sender=self, request=request)

    def create(self, request):
        signals.entry_request_started.send(sender=self, request=request)


class ExpressiveHandler(BaseHandler):
    model = ExpressiveSampleModel
    fields = ("title", "content", ("comments", ("content",)))

    @classmethod
    def comments(cls, em):
        return em.comments.all()

    def read(self, request):
        inst = ExpressiveSampleModel.objects.all()

        return inst

    def create(self, request):
        if request.piston_content_type and request.data:
            data = request.data

            em = self.model(title=data["title"], content=data["content"])
            em.save()

            for comment in data["comments"]:
                Comment(parent=em, content=comment["content"]).save()

            return rc.CREATED
        else:
            super().create(request)


class AbstractHandler(BaseHandler):
    fields = ("id", "some_other", "some_field")
    model = InheritedModel

    def read(self, request, id_=None):
        if id_:
            return self.model.objects.get(pk=id_)
        else:
            return super().read(request)


class PlainOldObjectHandler(BaseHandler):
    allowed_methods = ("GET",)
    fields = ("type", "field")
    model = PlainOldObject

    def read(self, request):
        return self.model()


class EchoHandler(BaseHandler):
    allowed_methods = ("GET", "HEAD")

    @validate(EchoForm, "GET")
    def read(self, request):
        return {"msg": request.form.cleaned_data["msg"]}


class ListFieldsHandler(BaseHandler):
    model = ListFieldsModel
    fields = ("id", "kind", "variety", "color")
    list_fields = ("id", "variety")


class Issue58Handler(BaseHandler):
    model = Issue58Model

    def read(self, request):
        return Issue58Model.objects.all()

    def create(self, request):
        if request.piston_content_type:
            data = request.data
            em = self.model(read=data["read"], model=data["model"])
            em.save()
            return rc.CREATED
        else:
            super(Issue58Model, self).create(request)


class ConditionalFieldsHandler(BaseHandler):
    model = ConditionalFieldsModel

    def fields(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return ("field_one", "field_two", "fk_field")
        return ("field_one",)

    def list_fields(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return ("field_one", "field_two")
        return ("field_two",)

    def read(self, request, object_id=None):
        qs = self.model.objects.all()
        if object_id:
            qs = qs.get(pk=object_id)
        return qs


class FileUploadHandler(BaseHandler):
    allowed_methods = ("POST",)

    @validate(FormWithFileField)
    def create(self, request):
        return {
            "chaff": request.form.cleaned_data["chaff"],
            "file_size": request.form.cleaned_data["le_file"].size,
        }


class CircularAHandler(BaseHandler):
    allowed_methods = ("GET",)
    fields = ("name", "link")
    model = CircularA


class CircularBHandler(BaseHandler):
    allowed_methods = ("GET",)
    fields = ("name", "link")
    model = CircularB


class CircularCHandler(BaseHandler):
    allowed_methods = ("GET",)
    fields = ("name", "link")
    model = CircularC
