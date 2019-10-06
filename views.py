from django.shortcuts import render, HttpResponse, redirect, reverse
from django.http import JsonResponse
from bbs import myforms, models
from PIL import Image, ImageDraw, ImageFont
import random
from io import BytesIO, StringIO
from django.contrib import auth
from django.contrib.auth.decorators import login_required
from django.db.models import Count,F
import json
from django.utils.safestring import mark_safe
from django.db import transaction
from bs4 import BeautifulSoup
import os
#官方提供的切割月份的模块
from django.db.models.functions import TruncMonth

"""
IO 是个内存管理器模块
BytesIO 存储二进制格式
StringIO 存储字符串格式

"""

"""
Image  生成图片
ImageDraw  在图片上写东西
ImageFont 控制字体样式
"""


# Create your views here.
#随机验证码
def get_random():
    return random.randint(0, 255), random.randint(0, 255), random.randint(0, 255)


# 注册功能
def register(request):
    form_obj = myforms.MyForm()
    if request.method == "POST":
        back_dic = {"code": 100, "msg": ''}
        # 校验用户信息是否合法
        form_obj = myforms.MyForm(request.POST)
        if form_obj.is_valid():
            # 获取前端传过来的字典
            clean_data = form_obj.cleaned_data
            # 在字典中剔除二次密码的键值对
            clean_data.pop("conf_password")
            # 手动获取用户头像
            user_file = request.FILES.get("myfile")
            if user_file:
                clean_data["avatar"] = user_file
            # 创建数据
            models.UserInfo.objects.create_user(**clean_data)
            back_dic["msg"] = "注册成功"
            back_dic["url"] = "/home/"
        else:
            back_dic["code"] = 101
            back_dic["msg"] = form_obj.errors
        return JsonResponse(back_dic)
    return render(request, "register.html", locals())


# 登录功能
def login(request):
    if request.method == "POST":
        # 定义一个空字典好返回给ajax请求
        back_dic = {"code": 100, "msg": ""}
        username = request.POST.get("username")
        password = request.POST.get("password")
        code = request.POST.get("code")
        # 先校验用户输入的验证码是否正确
        if request.session.get("code").lower() == code.lower():
            # 校验数据中用户名和密码是否正确
            user_obj = auth.authenticate(username=username, password=password)
            # 如果该用户存在
            if user_obj:
                # 保存用户的登录状态
                auth.login(request, user_obj)
                back_dic["msg"] = "登陆成功"
                back_dic["url"] = "/home/"
            else:
                back_dic["msg"] = "用户或密码错误"
                back_dic["code"] = 101
        else:
            back_dic["code"] = 102
            back_dic["msg"] = "验证码输入错误"
        return JsonResponse(back_dic)
    return render(request, "login.html")


# 主页
def home(request):
    article_list = models.Article.objects.all()
    return render(request, "home.html", locals())


# 注销
@login_required
def logout(request):
    auth.logout(request)
    return redirect(reverse("home"))


# 更改密码
@login_required
def set_password(request):
    # 判断是否是ajax请求
    if request.is_ajax():
        back_dic = {"code": 100, "msg": ""}
        old_password = request.POST.get("old_password")
        new_password = request.POST.get("new_password")
        conf_password = request.POST.get("conf_password")
        # 判断原始密码是否正确
        is_right = request.user.check_password(old_password)
        if is_right:
            # 判断两次密码是否输入相等
            if new_password == conf_password:
                # 设置新密码
                request.user.set_password(new_password)
                # 保存新密码
                request.user.save()
                back_dic["msg"] = "修改成功"
                back_dic["url"] = "/login/"
            else:
                back_dic["code"] = 102
                back_dic["msg"] = "两次密码输入不一致"
        else:
            back_dic["code"] = 101
            back_dic["msg"] = "原始密码输入错误"
        return JsonResponse(back_dic)


# 验证码
def get_code(request):
    # img_obj = Image.new("RGB",(230,33),get_random())
    # io_obj = BytesIO()
    # img_obj.save(io_obj,"png")
    # return HttpResponse(io_obj.getvalue()) #从内存对象中获取二进制数据

    # 直接在产生的图片上写验证码
    img_obj = Image.new("RGB", (230, 33), get_random())
    # 生成一个可以在图片上鞋子的画笔
    img_draw = ImageDraw.Draw(img_obj)
    img_font = ImageFont.truetype("static/font/SG.ttf", 30)
    io_obj = BytesIO()

    # 随机数验证码
    code = ""
    for i in range(5):
        upper_str = chr(random.randint(65, 90))
        lower_str = chr(random.randint(97, 122))
        number_str = str(random.randint(0, 9))
        choice_code = random.choice([upper_str, lower_str, number_str])
        # 写在图片上
        img_draw.text((20 + i * 45, 0), choice_code, get_random(), font=img_font)
        code += choice_code
    # 将随机产生的验证码存入session中
    request.session["code"] = code
    # 将写了验证码的图保存下来
    img_obj.save(io_obj, "png")
    return HttpResponse(io_obj.getvalue())

#个人站点
def site(request,username,**kwargs):
    #先获取用户用户名，查看用户是否存在
    user_obj = models.UserInfo.objects.filter(username=username).first()
    if not user_obj :
        return render(request,"error.html")
    #获取个人站点
    blog = user_obj.blog
    #查询当前用户的所有个人文章
    article_list = models.Article.objects.filter(blog=blog)
    if kwargs:

        condition = kwargs.get("condition")

        param = kwargs.get("param")
        if condition == "category":
            article_list = article_list.filter(category_id=param)
        elif condition == "tag":
            article_list = article_list.filter(tag__id=param)
        else:
            year,month = param.split("-")
            article_list = article_list.filter(create_time__year=year,create_time__month=month)
    #查询当前用户每一个分类的下的文章数
    category_list = models.Category.objects.filter(blog=blog).annotate(c=Count("article")).values("name","c","pk")
    #查询当前用户每个标签下的文章数
    tag_list = models.Tag.objects.filter(blog=blog).annotate(c=Count("article")).values("name","c","pk")
    #获取当前用户归档文章
    date_list = models.Article.objects.filter(blog=blog).annotate(month=TruncMonth("create_time")).values("month").annotate(c=Count("pk")).values_list("month","c")
    l = []
    for i in date_list:
        l.append(i)
    l.sort(reverse=True)


    return render(request,"site.html",locals())

#个人文章详情
def article_detail(request,username,article_id):
    #先获取用户用户名 查看是否存在
    user_obj = models.UserInfo.objects.filter(username=username).first()
    if not user_obj :
        #如果用户不存在则返回一个错误页面
        return render(request,"error.html")
    #获取当前用户blog表
    blog = user_obj.blog
    #根据文章ID查询出对应的文章并展示到前端
    article_obj = models.Article.objects.filter(pk=article_id).first()
    #获取当前文章的评论
    comment_list = models.Comment.objects.filter(article=article_obj)
    return render(request,"article.html",locals())

#点赞点踩
def up_down(request):
    if request.is_ajax():
        back_dic = {"code":100,"msg":""}
        #先校验用户是否登录
        if request.user.is_authenticated():
            article_id = request.POST.get("article_id")
            is_up = request.POST.get("is_up")
            #将字符串形式的js布尔值转换成后端的Python布尔值
            is_up = json.loads(is_up)
            #校验当前文章是否是当前用户自己所写的
            article_obj = models.Article.objects.filter(pk=article_id).first()
            if not article_obj.blog.userinfo == request.user:
                #校验当前用户是否已经给当前文章点过赞或踩
                is_click = models.Up_Down.objects.filter(article=article_obj,user=request.user)
                if not is_click:
                    #操作数据库 记录数据库 需要同步文章表里的普通字段
                    if is_up:
                        #如果是赞 先把文章表里的普通点赞字段加1
                        models.Article.objects.filter(pk=article_id).update(up_down=F('up_num')+1)
                        back_dic["msg"] = '点赞成功'
                    else:
                        #如果是踩， 先把文章表里面的普通点踩字段加1
                        models.Article.objects.filter(pk=article_id).update(down_num=F('down_num')+1)
                        back_dic["msg"] = "点踩成功"
                    #操作点赞点踩表
                    models.Up_Down.objects.create(user=request.user,article=article_obj,is_up=is_up)
                else:
                    back_dic["code"] = 101
                    back_dic["msg"] = "你已经点过了"
            else:
                back_dic["code"] = 102
                back_dic["msg"] = "不可以给自己点赞"
        else:
            back_dic["code"] = 103
            back_dic["msg"] = mark_safe("请先<a href='/login/'>登录</a>")
        return JsonResponse(back_dic)

def comment(request):
    if request.is_ajax():
        back_dic = {"code":100,"msg":""}
        #再校验后端最后一次用户是否登录
        if request.user.is_authenticated():
            content = request.POST.get("content")
            article_id = request.POST.get("article_id")
            parentId = request.POST.get("parentId")
            #文章评论数与普通字段同步
            with transaction.atomic():
                models.Comment.objects.create(user=request.user,article_id=article_id,content=content,parent_id=parentId)
                #更新评论数
                models.Article.objects.filter(pk=article_id).update(comment_num= F('comment_num')+1)
            back_dic["msg"] = "ok"
        else:
            back_dic["code"] = 101
            back_dic["msg"] = mark_safe("请先<a href='/login/'>登录</a>")

        return JsonResponse(back_dic)

#后台管理
from utils.mypage import Pagination
@login_required
def backend (request):
    article_list = models.Article.objects.filter(blog=request.user.blog)
    page_obj = Pagination(current_page=request.GET.get('page',1),all_count=article_list.count(),per_page_num=10)
    page_queryset = article_list[page_obj.start:page_obj.end]
    return render(request,'backend/backend.html',locals())



#添加文章
def add_article(request):
    if request.method == "POST":
        title = request.POST.get('title')
        content = request.POST.get('content')
        tags = request.POST.get('tag')
        category_id = request.POST.get('category')

        soup = BeautifulSoup(content,'html.parser')
        for tag in soup.find_all():
            if tag.name == 'script':
                tag.decompose()

        desc = soup.text[0:150]

        article_obj = models.Article.objects.create(title=title,desc=desc,content=str(soup),category_id=category_id,blog=request.user.blog)

        b_list = []
        for tag_id in tags:
            b_list.append(models.Article2Tag(article=article_obj,tag_id=tag_id))
        models.Article2Tag.objects.bulk_create(b_list)
        return redirect('/backend/')
    tag_list = models.Tag.objects.filter(blog=request.user.blog)
    category_list = models.Category.objects.filter(blog=request.user.blog)
    return render(request,'backend/add_article.html',locals())



from bbs2 import settings
#上传图片
def upload_img(request):
    if request.method == 'POST':
        file_obj = request.FILES.get('imgFile')
        #手动先拼接图片所在的文件路径
        base_path = os.path.join(settings.BASE_DIR,'media','article_img')
        #判断路径是否存在
        if not os.path.exists(base_path):
            os.mkdir(base_path)
        #手动拼接文件路径
        file_path = os.path.join(base_path,file_obj.name)
        #文件操作
        with open(file_path,'wb') as f :
            for line in file_obj:
                f.write(line)
        back_dic = {
            'error':0,
            'url':'/media/article_img/%s'%file_obj.name
        }
        return JsonResponse(back_dic)



#修改头像
def edit_avatar(request):
    if request.method == 'POST':
        file_obj = request.POST.get('myfile')
        if file_obj:
            request.uset.avatar = file_obj
            request.user.save()
        return redirect('/%s/'%request.user.username)
    return render(request,'edit_avatar1.html')





