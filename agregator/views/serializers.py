from rest_framework import generics
from agregator.models import User, Act, ScientificReport, TechReport, OpenLists, UserTasks, \
    ArchaeologicalHeritageSite, IdentifiedArchaeologicalHeritageSite, ObjectAccountCard, CommercialOffers, GeoObject, \
    GeojsonData, \
    Chat, Message
from agregator.serializers import UserSerializer, ActSerializer, ScientificReportSerializer, \
    TechReportSerializer, OpenListsSerializer, ObjectAccountCardSerializer, ArchaeologicalHeritageSiteSerializer, \
    IdentifiedArchaeologicalHeritageSiteSerializer, CommercialOffersSerializer, GeoObjectSerializer, \
    GeojsonDataSerializer, ChatSerializer, MessageSerializer


class UserList(generics.ListAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer


class UserDetail(generics.RetrieveAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer


class ActList(generics.ListAPIView):
    queryset = Act.objects.all()
    serializer_class = ActSerializer


class ActDetail(generics.RetrieveAPIView):
    queryset = Act.objects.all()
    serializer_class = ActSerializer


class ScientificReportList(generics.ListAPIView):
    queryset = ScientificReport.objects.all()
    serializer_class = ScientificReportSerializer


class ScientificReportDetail(generics.RetrieveAPIView):
    queryset = ScientificReport.objects.all()
    serializer_class = ScientificReportSerializer


class TechReportList(generics.ListAPIView):
    queryset = TechReport.objects.all()
    serializer_class = TechReportSerializer


class TechReportDetail(generics.RetrieveAPIView):
    queryset = TechReport.objects.all()
    serializer_class = TechReportSerializer


class OpenListsList(generics.ListAPIView):
    queryset = OpenLists.objects.all()
    serializer_class = OpenListsSerializer


class OpenListsDetail(generics.RetrieveAPIView):
    queryset = OpenLists.objects.all()
    serializer_class = OpenListsSerializer


class ObjectAccountCardList(generics.ListAPIView):
    queryset = ObjectAccountCard.objects.all()
    serializer_class = ObjectAccountCardSerializer


class ObjectAccountCardDetail(generics.RetrieveAPIView):
    queryset = ObjectAccountCard.objects.all()
    serializer_class = ObjectAccountCardSerializer


class ArchaeologicalHeritageSiteList(generics.ListAPIView):
    queryset = ArchaeologicalHeritageSite.objects.all()
    serializer_class = ArchaeologicalHeritageSiteSerializer


class ArchaeologicalHeritageSiteDetail(generics.RetrieveAPIView):
    queryset = ArchaeologicalHeritageSite.objects.all()
    serializer_class = ArchaeologicalHeritageSiteSerializer


class IdentifiedArchaeologicalHeritageSiteList(generics.ListAPIView):
    queryset = IdentifiedArchaeologicalHeritageSite.objects.all()
    serializer_class = IdentifiedArchaeologicalHeritageSiteSerializer


class IdentifiedArchaeologicalHeritageSiteDetail(generics.RetrieveAPIView):
    queryset = IdentifiedArchaeologicalHeritageSite.objects.all()
    serializer_class = IdentifiedArchaeologicalHeritageSiteSerializer


class CommercialOffersList(generics.ListAPIView):
    queryset = CommercialOffers.objects.all()
    serializer_class = CommercialOffersSerializer


class CommercialOffersDetail(generics.RetrieveAPIView):
    queryset = CommercialOffers.objects.all()
    serializer_class = CommercialOffersSerializer


class GeoObjectList(generics.ListAPIView):
    queryset = GeoObject.objects.all()
    serializer_class = GeoObjectSerializer


class GeoObjectDetail(generics.RetrieveAPIView):
    queryset = GeoObject.objects.all()
    serializer_class = GeoObjectSerializer


class GeojsonDataList(generics.ListAPIView):
    queryset = GeojsonData.objects.all()
    serializer_class = GeojsonDataSerializer


class GeojsonDataDetail(generics.RetrieveAPIView):
    queryset = GeojsonData.objects.all()
    serializer_class = GeojsonDataSerializer


class ChatList(generics.ListAPIView):
    queryset = Chat.objects.all()
    serializer_class = ChatSerializer


class ChatDetail(generics.RetrieveAPIView):
    queryset = Chat.objects.all()
    serializer_class = ChatSerializer


class MessageList(generics.ListAPIView):
    queryset = Message.objects.all()
    serializer_class = MessageSerializer


class MessageDetail(generics.RetrieveAPIView):
    queryset = Message.objects.all()
    serializer_class = MessageSerializer
