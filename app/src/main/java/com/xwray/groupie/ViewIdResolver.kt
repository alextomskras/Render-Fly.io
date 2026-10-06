package com.xwray.groupie

/** Имена id из layout-файлов -> R.id.* (замена удалённого Kotlin Synthetics). */
object ViewIdResolver {
    fun idOf(name: String): Int = when (name) {
        "already_have_accaunt_text_view" -> com.example.fess.kotlinmassage1.R.id.already_have_accaunt_text_view
        "back_to_register_login" -> com.example.fess.kotlinmassage1.R.id.back_to_register_login
        "edittext_chat_log" -> com.example.fess.kotlinmassage1.R.id.edittext_chat_log
        "email_edittext_login" -> com.example.fess.kotlinmassage1.R.id.email_edittext_login
        "email_edittext_register" -> com.example.fess.kotlinmassage1.R.id.email_edittext_register
        "image_send_button_chat_log" -> com.example.fess.kotlinmassage1.R.id.image_send_button_chat_log
        "imageview_chat_from_row" -> com.example.fess.kotlinmassage1.R.id.imageview_chat_from_row
        "imageview_chat_from_row2" -> com.example.fess.kotlinmassage1.R.id.imageview_chat_from_row2
        "imageview_chat_to_row" -> com.example.fess.kotlinmassage1.R.id.imageview_chat_to_row
        "imageview_chat_to_row2" -> com.example.fess.kotlinmassage1.R.id.imageview_chat_to_row2
        "imageview_latest_message" -> com.example.fess.kotlinmassage1.R.id.imageview_latest_message
        "imageview_latest_message1" -> com.example.fess.kotlinmassage1.R.id.imageview_latest_message1
        "imageview_new_message" -> com.example.fess.kotlinmassage1.R.id.imageview_new_message
        "kartinka_chat_from_row2" -> com.example.fess.kotlinmassage1.R.id.kartinka_chat_from_row2
        "kartinka_chat_to_row2" -> com.example.fess.kotlinmassage1.R.id.kartinka_chat_to_row2
        "kartinka_imageview_latest_message" -> com.example.fess.kotlinmassage1.R.id.kartinka_imageview_latest_message
        "login_button_login" -> com.example.fess.kotlinmassage1.R.id.login_button_login
        "password_edittext_login" -> com.example.fess.kotlinmassage1.R.id.password_edittext_login
        "password_edittext_register" -> com.example.fess.kotlinmassage1.R.id.password_edittext_register
        "recyclerview_chat_log" -> com.example.fess.kotlinmassage1.R.id.recyclerview_chat_log
        "recyclerview_latest_messages" -> com.example.fess.kotlinmassage1.R.id.recyclerview_latest_messages
        "recyclerview_newmessage" -> com.example.fess.kotlinmassage1.R.id.recyclerview_newmessage
        "register_button_register" -> com.example.fess.kotlinmassage1.R.id.register_button_register
        "select_photo_button_register" -> com.example.fess.kotlinmassage1.R.id.select_photo_button_register
        "select_photoview_image_send" -> com.example.fess.kotlinmassage1.R.id.select_photoview_image_send
        "select_photoview_register" -> com.example.fess.kotlinmassage1.R.id.select_photoview_register
        "send_button_chat_log" -> com.example.fess.kotlinmassage1.R.id.send_button_chat_log
        "textDate_message_time2" -> com.example.fess.kotlinmassage1.R.id.textDate_message_time2
        "textView_chat_from_message_time2" -> com.example.fess.kotlinmassage1.R.id.textView_chat_from_message_time2
        "textView_chat_to_message_time2" -> com.example.fess.kotlinmassage1.R.id.textView_chat_to_message_time2
        "textView_message_time" -> com.example.fess.kotlinmassage1.R.id.textView_message_time
        "textView_to_message_time" -> com.example.fess.kotlinmassage1.R.id.textView_to_message_time
        "text_kartinka_textview_latest_message3" -> com.example.fess.kotlinmassage1.R.id.text_kartinka_textview_latest_message3
        "text_textview_latest_message" -> com.example.fess.kotlinmassage1.R.id.text_textview_latest_message
        "textview_from_row" -> com.example.fess.kotlinmassage1.R.id.textview_from_row
        "textview_to_row" -> com.example.fess.kotlinmassage1.R.id.textview_to_row
        "username_edittext_register" -> com.example.fess.kotlinmassage1.R.id.username_edittext_register
        "username_kartinka_textview_latest_message" -> com.example.fess.kotlinmassage1.R.id.username_kartinka_textview_latest_message
        "username_textview_latest_message" -> com.example.fess.kotlinmassage1.R.id.username_textview_latest_message
        "username_textview_new_message" -> com.example.fess.kotlinmassage1.R.id.username_textview_new_message
        else -> 0
    }
}
