import json
from channels.generic.websocket import WebsocketConsumer
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from asgiref.sync import async_to_sync


from .models import *




class ChatroomConsumer(WebsocketConsumer):
    '''
    Это класс, который обрабатывает соединения WebSocket для реального времени.
    Когда пользователь подключается к чату через WebSocket, создается соединение,
    и сообщения рассылаются другим пользователям в этой комнате чата.
    '''
    def connect(self):
        self.user = self.scope['user'] # Получаем пользователя, который открыл WebSocket
        self.chatroom_name = self.scope['url_route']['kwargs']['chatroom_name'] # Получаем имя комнаты из URL. Например: /ws/chat/room_name/
        self.chatroom = get_object_or_404(ChatGroup, group_name=self.chatroom_name)


        async_to_sync(self.channel_layer.group_add)(
            self.chatroom_name, self.channel_name
        )
        # Добавляем текущее соединение в группу (группа = чат-комната).

        # добавление онлайн пользователей
        if self.user not in self.chatroom.user_online.all():
            self.chatroom.user_online.add(self.user)
            self.update_online_count()


        self.accept() # Подтверждаем соединение WebSocket.


    def disconnect(self, close_code):
        async_to_sync(self.channel_layer.group_discard)(
            self.chatroom_name, self.channel_name
        ) # Удаляем текущее соединение из группы (комнаты чата).

        if self.user in self.chatroom.user_online.all():
            self.chatroom.user_online.remove(self.user)
            self.update_online_count()




    def receive(self, text_data):
        text_data_json = json.loads(text_data)  # Раскодируем сообщение JSON от клиента.
        body = text_data_json['body']  # Извлекаем текст сообщения.

        message = GroupMessage.objects.create(
            body=body,  # Сохраняем текст сообщения.
            author=self.user,  # Автор сообщения — текущий пользователь.
            group=self.chatroom  # Комната, в которой отправлено сообщение.
        )

        event = {
            'type': 'message_handler',  # Указываем тип события (обработчик сообщения).
            'message_id': message.pk  # ID созданного сообщения.
        }

        async_to_sync(self.channel_layer.group_send)(
            self.chatroom_name, event
        )
        # Отправляем это событие всем участникам группы (комнаты).

    def message_handler(self, event):
        message_id = event['message_id']  # Извлекаем ID сообщения из события.
        message = GroupMessage.objects.get(id=message_id)  # Загружаем сообщение из базы данных.

        context = {
            'message': message,  # Передаем объект сообщения в шаблон.
            'user': self.user  # Передаем текущего пользователя.
        }

        html = render_to_string("a_rtchat/partials/chat_message_p.html", context=context)
        # Рендерим HTML для сообщения (например, <div>...</div>).

        self.send(text_data=html)  # Отправляем HTML клиенту через WebSocket.


    def update_online_count(self):
        online_count = self.chatroom.user_online.count()
        event = {
            "type": "online_count_handler",
            "online_count": online_count
        }
        async_to_sync(self.channel_layer.group_send)(self.chatroom_name, event)


    def online_count_handler(self, event):
        online_count = event["online_count"]
        html = render_to_string("a_rtchat/partials/online_count.html", {'online_count': online_count})
        self.send(text_data=html)





